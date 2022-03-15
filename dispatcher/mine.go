package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"sync/atomic"

	"cloud.google.com/go/pubsub"
	"github.com/google/go-github/v43/github"
	"golang.org/x/oauth2"

	"github.com/rs/zerolog/log"
	"github.com/scylladb/go-set/strset"
	//"zntr.io/typogenerator"
	//"zntr.io/typogenerator/mapping"
	//"zntr.io/typogenerator/strategy"
)

// Describes the payload for an individual target fork that is enqueued to the
// analyzer for static analysis
type Fork struct {
	Parent string
	Target string
	Token  string
}

type ForkFinder struct {
	Ctx         context.Context
	Inputs      *JobPayload
	Client      *github.Client
	PubsubTopic *pubsub.Topic
	Forks       []*Fork
	Cache       *strset.Set
}

func NewForkFinder(ctx context.Context, payload *JobPayload) (*ForkFinder, error) {
	log.Debug().Msg("Creating authenticated GitHub client")
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: payload.Token},
	)
	tc := oauth2.NewClient(ctx, ts)
	client := github.NewClient(tc)

	log.Info().Msg("Checking if user can write to target repo from API token")
	canWrite, err := CheckRepoOwner(ctx, client, payload.Repo)
	if err != nil {
		return nil, err
	}
	if !canWrite {
		return nil, fmt.Errorf("ForkFinder: user cannot write to target repository")
	}

	projectID := os.Getenv("GOOGLE_PROJECT_ID")
	if projectID == "" {
		return nil, fmt.Errorf("GOOGLE_PROJECT_ID path not specified as envvar")
	}

	topicID := os.Getenv("ANALYSIS_QUEUE")
	if topicID == "" {
		return nil, fmt.Errorf("ANALYSIS_QUEUE topic envvar not specified as envvar")
	}

	log.Debug().Msgf("Creating pubsub client and getting topic '%s'", topicID)
	pubsubClient, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		return nil, fmt.Errorf("pubsub.NewClient: %v", err)
	}
	//defer pubsubClient.Close()
	topic := pubsubClient.Topic(topicID)

	return &ForkFinder{
		Ctx:         ctx,
		Inputs:      payload,
		PubsubTopic: topic,
		Client:      client,
		Forks:       []*Fork{},
		Cache:       strset.New(),
	}, nil
}

// Helper to make sure that user can actually write to the target repository
func CheckRepoOwner(ctx context.Context, client *github.Client, repoName string) (bool, error) {
	// get current user from the token
	user, _, err := client.Users.Get(ctx, "")
	if err != nil {
		return false, err
	}
	currentUser := user.GetLogin()
	log.Debug().Msgf("Current GitHub user: %s", currentUser)

	// get all collaborators of the repository
	repo := strings.Split(repoName, "/")
	opt := github.ListCollaboratorsOptions{}
	collabs, _, err := client.Repositories.ListCollaborators(ctx, repo[0], repo[1], &opt)
	if err != nil {
		return false, err
	}

	log.Info().Msgf("Getting collaborators for %s", repoName)
	for _, collaborator := range collabs {
		if collaborator.GetLogin() == currentUser {
			log.Debug().Msg("API token can write to repo, progressing")
			return true, nil
		}
	}
	return false, nil
}

// With an instantiated `ForkFinder`, dispatch our API and fuzzing heuristics asynchronously,
// caching repository names that are found.
func (f *ForkFinder) FindAndDispatch(unlinked_typos bool) error {
	log.Info().Msgf("Recovering valid forks for repository %s", f.Inputs.Repo)
	if err := f.RecoverValidForks(); err != nil {
		return err
	}

	/*
		if unlinked_typos {
			if err := f.FuzzRepo(); err != nil {
				return err
			}
		}
	*/

	var wg sync.WaitGroup
	var totalErrors uint64

	log.Info().Msgf("Publishing %d forks for analysis", len(f.Forks))
	for _, fork := range f.Forks {
		payload, err := json.Marshal(*fork)
		if err != nil {
			return err
		}

		result := f.PubsubTopic.Publish(f.Ctx, &pubsub.Message{
			Data: payload,
		})
		wg.Add(1)

		// The Get method blocks until a server-generated ID or
		// an error is returned for the published message.
		go func(res *pubsub.PublishResult) {
			defer wg.Done()
			id, err := res.Get(f.Ctx)
			if err != nil {
				log.Error().Msgf("Failed to publish: %v", err)
				atomic.AddUint64(&totalErrors, 1)
				return
			}
			log.Info().Msgf("Published msg with ID: %v", id)
		}(result)
	}
	wg.Wait()

	if totalErrors > 0 {
		return fmt.Errorf("%d of %d messages did not publish successfully", totalErrors, len(f.Forks))
	}
	return nil
}

/*
// Given a repository, fuzz the owner and repo names to detect for "unlinked" forks.
// TODO: limit strategies to limit API invocations
func (f *ForkFinder) FuzzRepo() error {
	strategies := []strategy.Strategy{
		strategy.Addition,
		strategy.BitSquatting,
		strategy.Homoglyph,
		strategy.Omission,
		strategy.Repetition,
		strategy.Transposition,
		strategy.Prefix,
		strategy.Hyphenation,
		strategy.VowelSwap,
		strategy.Replace(mapping.English),
		strategy.DoubleHit(mapping.English),
		strategy.Similar(mapping.English),
	}

	// check for
	results, err := typogenerator.Fuzz(f.Owner, strategies...)
	if err != nil {
		return err
	}
	return nil
}
*/

// Given a repository name, create an authenticated client and recover
// all valid forks, including all subforks for that repo.
func (f *ForkFinder) RecoverValidForks() error {
	opts := github.RepositoryListForksOptions{
		Sort: "newest",
		ListOptions: github.ListOptions{
			PerPage: 100,
		},
	}

	// stores all the parent repos we have yet visited
	visited := []string{f.Inputs.Repo}

	// do a depth-first search, and traverse each fork for further children that should also be enqueued
	log.Info().Msg("Iterating and sanity checking recovered forks")
	for {

		// stop enqueing once we're all done
		if len(visited) == 0 {
			break
		}
		log.Debug().Msgf("%d left to visit", len(visited))

		// pop from visited and get owner and name
		repoName := Pop(&visited)
		repo := strings.Split(repoName, "/")

		// enumerate forks while dealing with pagination
		for {
			forks, res, err := f.Client.Repositories.ListForks(f.Ctx, repo[0], repo[1], &opts)
			if err != nil {
				return err
			}

			for _, fork := range forks {
				name := fork.GetFullName()

				// sanity check fork for existence
				log.Debug().Msgf("%s - checking if private repository", name)
				if fork.GetPrivate() {
					log.Printf("Skipping %s, is a private repo", name)
					continue
				}

				// it appears sometimes the repo is actually private or recently deleted,
				// do a second check to validate that is actually the case
				log.Debug().Msgf("%s - second existence check", name)
				ok, err := DirtyExistenceCheck(name)
				if err != nil {
					return err
				}
				if !ok {
					log.Debug().Msgf("%s - skipping may be private or deleted", name)
					continue
				}

				// traverse further if there are subforks
				count := fork.GetForksCount()
				if count != 0 {
					log.Debug().Msgf("%s - contains %d children forks to traverse", name, count)
					visited = append(visited, *fork.FullName)
				}

				log.Info().Msgf("%s - good to publish", name)
				fork := Fork{
					Parent: repoName,
					Target: name,
					Token:  f.Inputs.Token,
				}

				f.Forks = append(f.Forks, &fork)
			}
			if res.NextPage == 0 {
				break
			}
			opts.Page = res.NextPage
		}
	}
	return nil
}

func (f *ForkFinder) Close() {
	f.PubsubTopic.Stop()
}

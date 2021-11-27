package main

import (
	"context"
	"log"
	"net/http"

	"github.com/google/go-github/v40/github"
	"golang.org/x/oauth2"
	//"zntr.io/typogenerator"
	//"zntr.io/typogenerator/mapping"
	//"zntr.io/typogenerator/strategy"
)

// Directly sends a request to the GitHub repository page to check if the
// repository exists or has recently become private.
func DirtyCheck(repoName string) (bool, error) {
	url := "https://github.com/" + repoName
	resp, err := http.Get(url)
	if err != nil {
		return false, err
	}

	if resp.StatusCode == 404 {
		return false, nil
	}
	return true, nil
}

/*
// Given a repository, fuzz the owner and repo names to detect for "unlinked" forks.
func TyposquatFuzzRepo(owner, payload *JobPayload) error {
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
	results, err := typogenerator.Fuzz(*input, strategies...)
	if err != nil {
		return err
	}
	return nil
}
*/

// Given a repository name, create an authenticated client and recover
// all valid forks, including all subforks for that repo.
func RecoverValidForks(ctx context.Context, payload *JobPayload) (*[]string, error) {
	log.Println("Creating authenticated GitHub client")
	ts := oauth2.StaticTokenSource(
		&oauth2.Token{AccessToken: payload.Token},
	)
	tc := oauth2.NewClient(ctx, ts)
	client := github.NewClient(tc)

	opts := github.RepositoryListForksOptions{
		Sort: "newest",
	}

	log.Println("Listing forks for repository")
	forks, _, err := client.Repositories.ListForks(ctx, payload.Owner, payload.Repo, &opts)
	if err != nil {
		return nil, err
	}

	finalForks := []string{}

	// do a depth-first search, and traverse each fork
	log.Println("Iterating and sanity checking recovered forks")
	for _, fork := range forks {
		name := fork.GetFullName()

		// sanity check fork for existence
		if fork.GetPrivate() {
			log.Printf("Skipping %s, is a private repo", name)
			continue
		}

		if ok, err := DirtyCheck(name); err != nil && !ok {
			log.Printf("Skipping %s, may be deleted", name)
			continue
		} else {
			return nil, err
		}

		// traverse further if there are subforks
		count := fork.GetForksCount()
		if count != 0 {
			// TODO
		}
		finalForks = append(finalForks, name)
	}
	return &finalForks, nil
}

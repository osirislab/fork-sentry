package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"sync"
	"sync/atomic"

	"cloud.google.com/go/pubsub"
)

// Helper that sends a request to the GitHub repository page to check if the
// repository exists or has recently become private.
func DirtyExistenceCheck(repoName string) (bool, error) {
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

// Given all the recovered forks for the current repository, enqueued to the analysis pubsub in parallel
// for analyzer module to
func DispatchForAnalysis(ctx context.Context, w io.Writer, forks []string) error {
	projectID := os.Getenv("GOOGLE_PROJECT_ID")
	topicID := os.Getenv("ANALYSIS_QUEUE")

	client, err := pubsub.NewClient(ctx, projectID)
	if err != nil {
		return fmt.Errorf("pubsub.NewClient: %v", err)
	}
	defer client.Close()

	var wg sync.WaitGroup
	var totalErrors uint64
	t := client.Topic(topicID)

	for _, fork := range forks {
		result := t.Publish(ctx, &pubsub.Message{
			Data: []byte(fork),
		})
		wg.Add(1)

		go func(res *pubsub.PublishResult) {
			defer wg.Done()
			// The Get method blocks until a server-generated ID or
			// an error is returned for the published message.
			id, err := res.Get(ctx)
			if err != nil {
				// Error handling code can be added here.
				fmt.Fprintf(w, "Failed to publish: %v", err)
				atomic.AddUint64(&totalErrors, 1)
				return
			}
			fmt.Fprintf(w, "Published msg with ID: %v\n", id)
		}(result)
	}
	wg.Wait()

	if totalErrors > 0 {
		return fmt.Errorf("%d of %d messages did not publish successfully", totalErrors, len(forks))
	}
	return nil
}

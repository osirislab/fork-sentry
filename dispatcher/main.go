package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"sync"
	"sync/atomic"

	"cloud.google.com/go/pubsub"
)

type JobPayload struct {
	Owner string `json:"owner"`
	Repo  string `json:"name"`
	Token string `json:"github_token"`
	API   string `json:"api_token"`
}

func main() {
	log.Print("Starting server...")
	http.HandleFunc("/dispatch", DispatchHandler)
	//http.HandleFunc("/", AdhocHandler)

	// Start HTTP server.
	log.Printf("Listening on port 8080")
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}

func DispatchHandler(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()

	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Printf("ioutil.ReadAll: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	log.Printf("Recovering payload for analysis")
	var payload JobPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		log.Printf("json.Unmarshal: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	if payload.Owner == "" || payload.Repo == "" {
		log.Println("repository payload incomplete")
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	repoName := payload.Owner + "/" + payload.Repo
	log.Printf("Recovering valid forks for repo %s", repoName)
	validForks, err := RecoverValidForks(ctx, &payload)
	if err != nil {
		log.Printf("valid fork recovery failed: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	log.Println(validForks)
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

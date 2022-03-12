package main

import (
	"context"
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
	"os"

	"github.com/didip/tollbooth/v6"
	"github.com/joho/godotenv"
)

type JobPayload struct {
	Repo  string `json:"repo"`
	Token string `json:"github_token"`
	API   string `json:"api_token"`
}

func init() {
	if os.Getenv("DEBUG") == "true" {
		err := godotenv.Load()
		if err != nil {
			panic(err)
		}
	}
}

func main() {
	lmt := tollbooth.NewLimiter(1, nil)

	log.Print("Starting server on port 8080...")
	http.Handle("/dispatch", tollbooth.LimitFuncHandler(lmt, DispatchHandler))
	http.HandleFunc("/health", HealthHandler)
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}

func HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusAccepted)
}

func DispatchHandler(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()

	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Fatalf("ioutil.ReadAll: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	log.Printf("Recovering payload for analysis")
	var payload JobPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		log.Fatalf("json.Unmarshal: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	if payload.Repo == "" {
		log.Fatal("Repository payload incomplete")
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// WIP: for now, check only against a single API token to restrict access
	rootToken := os.Getenv("ROOT_API_TOKEN")
	if payload.API != rootToken {
		log.Fatal("Invalid API token")
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	// TODO: check to see if analysis can be dispatched again

	log.Println("Initial payload is good, responding and continuing with task")
	w.WriteHeader(http.StatusAccepted)

	go func() {
		log.Printf("Recovering valid forks for repo '%s'", payload.Repo)

		ff, err := NewForkFinder(ctx, &payload)
		if err != nil {
			log.Fatalf("Instantiating ForkFinder failed: %s", err)
			http.Error(w, "Bad Request", http.StatusBadRequest)
			return
		}
		defer ff.Close()

		if err := ff.FindAndDispatch(false); err != nil {
			log.Fatalf("Excavating and dispatching forks failed: %s", err)
			http.Error(w, "Bad Request", http.StatusBadRequest)
			return
		}

		log.Printf("Finalized dispatching analysis for `%s", payload.Repo)
	}()
}

func CheckApiToken(token string) (bool, error) {
	return true, nil
}

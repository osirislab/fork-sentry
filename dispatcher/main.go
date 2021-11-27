package main

import (
	"context"
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
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

	ff, err := NewForkFinder(ctx, &payload)
	if err != nil {
		log.Println("instantiating ForkFinder failed")
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	if err := ff.FindAndDispatch(); err != nil {
		log.Println("excavating and dispatching forks failed")
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
}

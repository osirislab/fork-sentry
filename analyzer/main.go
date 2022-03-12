package main

import (
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
	"os"

	"github.com/joho/godotenv"
)

// PubSubMessage is the payload of a Pub/Sub event.
// https://cloud.google.com/pubsub/docs/reference/rest/v1/PubsubMessage
type ForkMessage struct {
	Message struct {
		Data []byte `json:"data,omitempty"`
		ID   string `json:"id"`
	} `json:"message"`
	Subscription string `json:"subscription"`
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
	log.Print("Starting server on port 8080...")
	http.HandleFunc("/", PubsubHandler)
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Fatal(err)
	}
}

func PubsubHandler(w http.ResponseWriter, r *http.Request) {
	var m ForkMessage
	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Printf("ioutil.ReadAll: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}
	if err := json.Unmarshal(body, &m); err != nil {
		log.Printf("json.Unmarshal: %v", err)
		http.Error(w, "Bad Request", http.StatusBadRequest)
		return
	}

	name := string(m.Message.Data)
	if name == "" {
		name = "World"
	}
	log.Printf("Hello %s!", name)
}

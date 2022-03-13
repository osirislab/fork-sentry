package main

import (
	"context"
	"encoding/json"
	"io/ioutil"
	"net/http"
	"os"

	"github.com/didip/tollbooth/v6"
	"github.com/joho/godotenv"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"

	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

// Body input the dispatcher must consume to kick off analysis
type JobPayload struct {
	Repo  string `json:"repo"`
	Token string `json:"github_token"`
	API   string `json:"api_token"`
}

// API token model for each sample
type ApiKey struct {
	gorm.Model
	Token    string
	LastUsed int64
}

func init() {
	debug := os.Getenv("DEBUG") == "true"
	if debug {
		err := godotenv.Load()
		if err != nil {
			panic(err)
		}
	}

	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	log.Logger = zerolog.New(os.Stdout).With().Timestamp().Logger()
	if debug {
		log.Logger = log.Output(zerolog.ConsoleWriter{Out: os.Stderr})
	}
}

func main() {
	lmt := tollbooth.NewLimiter(1, nil)

	log.Info().Msg("Starting server on port 8080...")
	http.Handle("/dispatch", tollbooth.LimitFuncHandler(lmt, DispatchHandler))
	http.HandleFunc("/health", HealthHandler)
	if err := http.ListenAndServe(":8080", nil); err != nil {
		log.Error().Msgf("%v", err)
	}
}

func HealthHandler(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusAccepted)
}

func DispatchHandler(w http.ResponseWriter, r *http.Request) {
	ctx := context.Background()

	if r.Body == http.NoBody {
		http.Error(w, "Bad Request: no body provided.", http.StatusBadRequest)
		return
	}

	body, err := ioutil.ReadAll(r.Body)
	if err != nil {
		log.Error().Msgf("ioutil.ReadAll: %v", err)
		http.Error(w, "Bad Request: cannot read body.", http.StatusBadRequest)
		return
	}

	log.Info().Msg("Recovering payload for analysis")
	var payload JobPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		log.Error().Msgf("json.Unmarshal: %v", err)
		http.Error(w, "Bad Request: cannot serialize body into JSON.", http.StatusBadRequest)
		return
	}

	if payload.Repo == "" {
		log.Error().Msg("Repository payload incomplete")
		http.Error(w, "Bad Request: no repository name specified.", http.StatusBadRequest)
		return
	}

	// WIP: for now, check only against a single API token to restrict access
	rootToken := os.Getenv("ROOT_API_TOKEN")
	if payload.API != rootToken {
		log.Error().Msg("Invalid API token")
		http.Error(w, "Bad Request: invalid API token specified.", http.StatusBadRequest)
		return
	}

	log.Info().Msg("Initial payload is good, responding and continuing with task")
	w.WriteHeader(http.StatusAccepted)

	ff, err := NewForkFinder(ctx, &payload)
	if err != nil {
		log.Error().Msgf("Instantiating ForkFinder failed: %s", err)
		http.Error(w, "Bad Request: cannot mine for forks.", http.StatusBadRequest)
		return
	}
	defer ff.Close()

	go func() {
		log.Info().Msgf("Recovering valid forks for repo '%s'", payload.Repo)

		if err := ff.FindAndDispatch(false); err != nil {
			log.Error().Msgf("Excavating and dispatching forks failed: %s", err)
			http.Error(w, "Bad Request: cannot mine for forks.", http.StatusBadRequest)
			return
		}

		log.Info().Msgf("Finalized dispatching analysis for `%s", payload.Repo)
	}()
}

func CheckApiToken(token string) (bool, error) {
	db, err := gorm.Open(sqlite.Open("test.db"), &gorm.Config{})
	if err != nil {
		panic("failed to connect database")
	}

	var api ApiKey
	db.First(&api, "token = ?", token)
	if api.Token == "" {
		return false, nil
	}

	// cloud users should not be dispatching analysis more than once every six hours
	//now := time.Now()
	//lastUsed := time.Unix(api.LastUsed, 0)

	return true, nil
}

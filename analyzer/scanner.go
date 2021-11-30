package main

import (
    "context"
    "io/ioutil"
    "log"

    "cloud.google.com/go/storage"
    "github.com/mirtchovski/clamav"
)

type Scanner struct {
    Buf []byte
}

// Given a newly enriched object in storage, pull down, read to
// buffer and prepare our environment to do static analysis.
func NewScanner(bucket, object string) (*Scanner, error) {
    ctx := context.Background()

    client, err := storage.NewClient(ctx)
    if err != nil {
        return nil, err
    }

    log.Printf("Pulling file from gs://%s/%s", bucket, object)
	rc, err := client.Bucket(bucket).Object(object).NewReader(ctx)
	if err != nil {
        return nil, err
	}
	defer rc.Close()
	body, err := ioutil.ReadAll(rc)
	if err != nil {
        return nil, err
	}

	return &Scanner{
		Buf: body,
	}, nil
}

func (s *Scanner) IsSimilar() (bool, error) {
    return false, nil
}


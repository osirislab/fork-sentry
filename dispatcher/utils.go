package main

import (
	"net/http"
)

func Pop(a *[]string) string {
	f := len(*a)
	rv := (*a)[f-1]
	*a = (*a)[:f-1]
	return rv
}

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

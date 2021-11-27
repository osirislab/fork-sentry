# Fork Sentry

Detect and alert on suspicious forks of your repository

## Introduction

__Fork Sentry__ is a [GitHub Action](https://github.com/features/actions) that reports on
suspicious forks of your repository that may be serving malicious artifacts.

In the past, __Fork Sentry__ has already found and taken down instances of:

* Typosquatted accounts serving modified releases
* Malicious cryptominers part of C2 infrastructures

(TODO: include writeups, and links to paper releases)

## Actions Usage

```yml
name: Check for suspicious forks
on:
  schedule:
    - cron: '0 10 * * 1' # Checks for updates every Monday at 10:00 AM

jobs:
  fork-sentry:
    runs-on: ubuntu-latest
    steps:
      - uses: ex0dus-0x/fork-sentry@v1.0
        with:

          # required for authentication and recovering forks
          github_token: ${{ secrets.GITHUB_TOKEN }}
          fork_sentry_token: ${{ secrets.FORK_SENTRY_API }}

          # if self-hosting, replace with dispatcher endpoint
          #infra_endpoint: https://fork-sentry-instance.example.com
```

## Implementation

## License

Fork Sentry is release under a Apache License 2.0 License

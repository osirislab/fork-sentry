#!/usr/bin/env python3
"""
alert.py

    Alert Function triggered by PubSub to output detected malicious forks to issue tracker.
"""
import json
import base64
from github import Github, RateLimitExceededException


def handler(request):
    """
    In the edge case where we've exhausted the rate limit from
    analysis earlier, backoff creating issue alerts until the next hour.
    """
    try:
        _handler(request)
    except RateLimitExceededException:
        return ("", 500)

    return ("", 204)


def _handler(request):
    """
    An alert may already be generated for a fork, so do a search for existing
    issues that may already rise
    """
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        return f"Bad Request: {msg}", 400
    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    data = envelope["message"]["data"]
    payload = base64.b64decode(data).decode("utf-8")
    payload = json.loads(payload)

    # create client for processing
    gh = Github(payload["token"])

    parent = payload["parent"]
    child = payload["name"]
    repo = gh.get_repo(parent)

    # get or create a Fork Sentry label for search and tagging issues

    # get all fork sentry issues and detect if this fork already has been picked up previously
    issues = gh.get_issues()
    for issue in issues:

        # if found, create a comment under the issue
        pass

    # create content for issue
    title = f":warning: Fork Sentry: {child} is potentially malicious"
    body = """## Suspicious Files & Indicators\n"""

    if payload["typosquatting"]:
        body += "The fork appears to be __typosquatting__ your repository, creating opportunities to get victims that misspell your repo's name.\n"

    for path, indicators in payload["suspicious"].items():
        pass

    repo.create_issue(title=title, body=body)

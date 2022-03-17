#!/usr/bin/env python3
"""
alert.py

    Alert Function triggered by PubSub to output detected malicious forks to issue tracker.
"""
import json
import base64
import logging

from google.cloud import logging as cloudlogging
from github import Github, RateLimitExceededException
from pytablewriter import MarkdownTableWriter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ensure logs can be seen by GCP
_client = cloudlogging.Client()
_loghandler = _client.get_default_handler()
logger.addHandler(_loghandler)

REPORT_LINK = "https://support.github.com/contact/report-abuse?category=report-abuse&report=other&report_type=unspecified"


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

    # get all fork sentry issues and detect if this fork already has been picked up previously
    # if found, create a comment under the issue instead
    logger.info("Checking for existing issues with the malicious fork")
    for issue in repo.get_issues():
        if child in issue.title and issue.state != "closed":
            return

    logger.info("Creating issue content to alert")

    title = f":warning: Fork Sentry: {child} fork is potentially malicious"
    body = f"""This is an automated issue created by [Fork Sentry](https://github.com/marketplace/actions/fork-sentry), which identified a fork of your repository that is possibly serving some form of malware.

## Detection Results

If the generated results warrant takedown, please click [here]({REPORT_LINK}) to file a report with GitHub Trust & Safety.
If this is a false positive, you may give this issue a :thumbsdown: so the team can better enhance our detection strategies.
"""

    if payload["typosquatting"]:
        body += "### Repository Typosquatting\n"
        body += "The fork's name, `{child}` appears to be __typosquatting__ your repository, creating opportunities to hack victims that misspell your repo's name.\n"

    if len(payload["sus_committed"]) != 0:
        body += "### Suspiciously Committed Files :file_folder:\n"
        body += "These are files committed to somewhere in the fork repository that were deemed malicious.\n"

        # TODO: make this better
        entries = []
        for entry in payload["sus_committed"]:
            iocs = ", ".join(entry["iocs"])
            entries += [[entry["path"], entry["sha256"], iocs]]

        # TODO: commit, branch, author, download link from our artifact storage
        writer = MarkdownTableWriter(
            headers=["Path", "SHA256", "Malware Indicators"],
            value_matrix=entries,
        )
        body += writer.dumps()
        body += "\n"

    if len(payload["sus_releases"]) != 0:
        body += "### Rogue Releases :package:\n"
        body += "These are artifacts found in the fork's GitHub Releases that were deemed malicious.\n"

        # TODO: make this better
        entries = []
        for entry in payload["sus_releases"]:
            iocs = ", ".join(entry["iocs"])
            tag = f"[{entry['tag']}]({entry['url']})"
            entries += [[tag, entry["path"], entry["sha256"], iocs]]

        writer = MarkdownTableWriter(
            headers=["Release", "Path", "SHA256", "Malware Indicators"],
            value_matrix=entries,
        )
        body += writer.dumps()
        body += "\n"

    # create new issue label if necessary
    label = None
    for l in repo.get_labels():
        if l.name == "Fork Sentry":
            label = l

    if label is None:
        logger.info("Creating new label for issue alert")
        label = repo.create_label(
            name="Fork Sentry", color="EF330A", description="Malicious forks."
        )

    # TODO: aggregate all public alerts generated for internal use
    logger.info("Finalizing GitHub alert")
    repo.create_issue(title=title, body=body, labels=[label])

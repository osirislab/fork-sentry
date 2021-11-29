#!/usr/bin/env python3
"""
main.py (WIP)

    Alert Function triggered by PubSub to output results to any
    variety of services that exist.

    Outputs we can ideally dispatch out to:
    * GitHub Comments (using authorization token)
    * Slack Channel
    * Threat Intelligence Products
"""
from github import Github


def handler(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <https://flask.palletsprojects.com/en/1.1.x/api/#flask.Flask.make_response>`.
    """
    request_json = request.get_json()
    gh_token = request_json["github"]
    return ""

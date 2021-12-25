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
import json
import base64
from github import Github


def handler(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values
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
    print(payload)
    return ""

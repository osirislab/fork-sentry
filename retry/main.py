#!/usr/bin/env python3
"""
retry.py

    Cloud Function triggered by an hourly scheduler to pull messages
    that haven't been processed due to a rate-limit and re-enqueue them.
"""
import json
import base64

from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1

subscriber = pubsub_v1.SubscriberClient()


def handler(request):
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

    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)

    # TODO: exit immediately if no messages to deal with

    # wrap subscriber to automatically call close
    with subscriber:
        try:
            streaming_pull_future.result(timeout=5)
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()

"""
main.py

    Pulls repositories from Pubsub to do fork analysis. Recovers all forks, and enqueues 
    fresh alerts to output.
"""
import os
import json
import base64
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, request

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

from repo_analysis import RepoAnalysis

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0,
)

app = Flask(__name__)


@app.route("/", methods=["POST"])
def handler():
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        return f"Bad Request: {msg}", 400
    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    # decode the message payload and recover metadata
    data = envelope["message"]["data"]
    payload = base64.b64decode(data).decode("utf-8")
    payload = json.loads(payload)

    repo = payload["Repo"]
    token = payload["Token"]
    tags = payload["Tags"]
    try:
        analysis = RepoAnalysis(repo, token)
        analysis.detect_suspicious()
    except Exception as err:
        print(f"Error for `{repo}`: {err}")
        sentry_sdk.capture_exception(err)

    return ("", 204)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

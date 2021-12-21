"""
repo_analysis.py

    Implements interface to support fork integrity analysis.
"""
import io
import os
import json
import logging
import shutil
import random
import string
import shutil
import mimetypes
import hashlib
import typing as t

import git
import lief
import clamd
import vt
import requests
from github import Github

from google.cloud import pubsub_v1, storage
from google.cloud import logging as cloudlogging

from scanner import IGNORE_SOURCE_EXTS, ARCHIVE_MIME

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# setup publisher to output queue
publisher = pubsub_v1.PublisherClient()
topic = f"projects/{os.getenv('GOOGLE_PROJECT_ID')}/topics/{os.getenv('ALERT_TOPIC')}"

# setup interface to storage
storage_client = storage.Client()
bucket = storage_client.bucket(os.getenv("INFECTED_BUCKET"))

# ensure logs can be seen by GCP
_client = cloudlogging.Client()
_handler = _client.get_default_handler()
logger.addHandler(_handler)

# static analysis scanner
scanner = clamd.ClamdUnixSocket()


class RepoAnalysis:
    """
    Implements an interface for conducting fork integrity analysis across a single repository.
    """

    def __init__(
        self,
        parent_name: str,
        repo_name: str,
        token: str,
        tags: t.List[str],
        vt_token: t.Optional[str] = None,
    ):
        self.gh = Github(token)

        # fork attributes
        self.token = token
        self.repo = self.gh.get_repo(repo_name)
        self.uuid = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(6)
        )
        self.fork_owner = self.repo.owner.login
        self.repo_name = self.repo.full_name
        self.branch = self.repo.default_branch

        # parent repo attributes
        self.parent = self.gh.get_repo(parent_name)
        self.orig_name = self.parent.full_name
        self.parent_branch = self.parent.default_branch

        # VT client
        self.vt_client = None
        if vt_token:
            self.vt_client = vt.Client("<apikey>")

        # tags parsed initially from the dispatcher
        self.tags = tags

    def analyze_artifact(self, path) -> t.Optional[str]:
        """
        Heuristics to check if a modified file is suspicious and should be enqueued for further analysis.
        """

        # TODO: will ignore source code changes for now
        _, ext = os.path.splitext(path)
        if ext in IGNORE_SOURCE_EXTS:
            return None

        with open(path, "rb") as fd:
            contents = fd.read()

        # stores hashes and results from scans
        finalized = {
            "sha256": hashlib.sha256(contents).hexdigest(),
            # "ssdeep": ssdeep.hash(contents),
            "tags": self.tags,
        }

        # determines if we should return results
        is_suspicious = False

        # trigger ClamAV scan first
        results = scanner.instream(io.BytesIO(contents))
        for path, tags in results.items():
            found, name = tags[0], tags[1]
            if found == "FOUND":
                finalized["tags"] += [f"clamav:{name}"]
                is_suspicious = True

        # file is a binary executable/library
        if lief.is_elf(path) or lief.is_pe(path) or lief.is_macho(path):
            finalized["tags"] += ["binary"]

            # TODO: check for similarity

            # TODO: virustotal enterprise
            if self.vt_client:
                pass

            is_suspicious = True

        # file is some compressed archive
        elif mimetypes.guess_type(path)[0] in ARCHIVE_MIME:
            finalized["tags"] += ["archive"]

            # TODO
            shutil.unpack_archive(path, self.uuid)

            is_suspicious = True

        # file is build script
        elif path.endswith(".sh") or "Makefile" in path:
            finalized["tags"] += ["build-script"]
            is_suspicious = True

        if not is_suspicious:
            return None
        else:
            return finalized

    def detect_suspicious(self):
        """
        Analyze an individual fork repository and detect suspicious artifacts and releases.
        """

        logger.debug(f"Analyzing {self.repo_name}")
        results = {
            "name": self.repo_name,
            "token": self.token,
            "suspicious": {},
            "file_deltas": [],
            "releases": {},
        }

        # find commits by the fork owner and/or user known as a contributor, and
        # detect if any of the changes are new artifacts we need to analyze
        logger.info(f"{self.repo_name}: checking for suspicious commits")

        # clone repository to temporary path with random ID to prevent concurrent containers
        # from cloning to the same spot
        path = self.repo.name + "-" + self.uuid
        if os.path.exists(path):
            shutil.rmtree(path)

        fork_repo = git.Repo.clone_from(self.repo.clone_url, path)

        # iterate over all branches, and find commits not by original contributors

        # add and sync with parent repo
        # git remote add upstream PARENT
        # git fetch upstream
        remote = fork_repo.create_remote("upstream", self.parent.clone_url)
        remote.fetch()

        # get number of commits the fork is ahead by
        # git rev-list --left-right --count origin/master...upstream/master
        count = fork_repo.git.rev_list(
            "--left-right",
            "--count",
            f"{self.branch}...upstream/{self.parent_branch}",
        )
        ahead = int(count.split("\t")[0])
        if ahead > 0:

            # run check against files that are recently created at HEAD
            # git --no-pager diff --name-only HEAD~{AHEAD}
            head = fork_repo.head.commit
            for diff in head.diff(f"HEAD~{ahead}").iter_change_type("D"):
                artifact = f"{path}/{diff.a_path}"

                logger.debug(f"Analyzing `{artifact}` for suspicious indicators")
                artifact_res = self.analyze_artifact(artifact)
                if artifact_res:

                    # create object name to store in infected bucket
                    base = diff.a_path.split("/")[-1]
                    object_name = self.orig_name + "/" + self.fork_owner + "/" + base
                    self._push_to_storage(artifact, object_name)

                    # filter out those with interesting results
                    results["suspicious"][diff.a_path] = artifact_res

                # record all files changed
                results["file_deltas"] += [diff.a_path]

        shutil.rmtree(path)

        # check if fork has releases that are not released by the original author
        logger.info(f"{self.repo_name} - checking for suspicious releases")
        for release in self.repo.get_releases():
            tag = release.tag_name

            results["releases"][tag] = []
            for asset in release.get_assets():

                filename = asset.name
                url = asset.browser_download_url

                # download file to disk
                resp = requests.get(url)
                with open(filename, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)

                logger.debug(f"Analyzing `{artifact}` for suspicious indicators")
                artifact_res = self.analyze_artifact(filename)
                if artifact_res:

                    # create object name to store in infected bucket
                    object_name = (
                        self.orig_name + "/" + self.fork_owner + "/" + filename
                    )
                    self._push_to_storage(artifact, object_name)

                    # filter out those with interesting results
                    results["suspicious"][filename] = artifact_res

                os.remove(filename)

                results["releases"][tag] += [
                    {
                        "name": filename,
                        "url": url,
                    }
                ]
                logger.debug(f"{asset.name}: {asset.browser_download_url}")

        self._generate_alerts(results)

    def _push_to_storage(self, path: str, dest: str) -> None:
        """
        Upload artifacts to storage for auxiliary analysis.
        """
        logger.info(f"Pushing potentially malicious artifact to `{dest}`")
        blob = bucket.blob(dest)
        blob.upload_from_filename(path)

    def _generate_alerts(self, results) -> None:
        """
        Helper to generate alerts to different sources if artifacts found are suspicious.
        """
        if (
            len(results["suspicious"]) == 0
            and len(results["releases"]) == 0
            and len(results["file_deltas"]) == 0
        ):
            logger.info(f"Nothing found for fork {self.repo_name}")
            return

        logger.info(f"Outputting alerts for `{self.repo_name}`")
        alerts = json.dumps(results, indent=2).encode("utf-8")
        publisher.publish(topic, alerts)

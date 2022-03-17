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
import difflib

import git
import lief
import clamd
import vt
import ssdeep
import requests
from github import Github
from sqlalchemy import create_engine

from google.cloud import pubsub_v1, storage
from google.cloud import logging as cloudlogging

from consts import IGNORE_SOURCE_EXTS, ARCHIVE_MIME

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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

# database url
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url, echo=True, future=True)

# malware signature scan
try:
    scanner = clamd.ClamdUnixSocket()
    scanner.ping()
except clamd.ConnectionError:
    logger.info("Attempting to connect to ClamAV through network socket")
    scanner = clamd.ClamdNetworkSocket()
    try:
        scanner.ping()
    except clamd.ConnectionError:
        logger.info("Cannot get bindings to ClamAV")
        scanner = None


class RepoAnalysis:
    """
    Implements an interface for conducting fork integrity analysis across a single fork repository.

    During analysis, recovers all interesting filetypes from both repository tree and branches, and
    applies malware detection techniques.
    """

    def __init__(
        self,
        parent_name: str,
        repo_name: str,
        token: str,
        vt_token: t.Optional[str] = None,
    ):
        self.gh = Github(token)
        self.token = token

        # fork attributes
        self.repo = self.gh.get_repo(repo_name)
        self.uuid = "".join(
            random.choice(string.ascii_uppercase + string.digits) for _ in range(6)
        )
        self.fork_owner = self.repo.owner.login
        self.repo_name = self.repo.full_name

        # parent repo attributes
        self.parent = self.gh.get_repo(parent_name)
        self.orig_name = self.parent.full_name
        self.repo_branches = list([b.name for b in self.parent.get_branches()])
        self.parent_default = self.parent.default_branch

        # Virustotal client
        self.vt_client = None
        if vt_token:
            self.vt_client = vt.Client(vt_token)

    def _analyze_artifact(self, path) -> t.Optional[t.Dict[str, str]]:
        """
        Heuristics to check if a modified file is suspicious and should be enqueued for further analysis.
        """

        # ignore source code changes for now
        _, ext = os.path.splitext(path)
        if ext in IGNORE_SOURCE_EXTS:
            return None

        # stores suspicious indicators
        iocs = []

        # stores all files to analyze, if more are extracted
        targets = []

        # binary parser helper
        is_bin = (
            lambda path: lief.is_elf(path) or lief.is_pe(path) or lief.is_macho(path)
        )

        # file is a binary executable/library
        if is_bin(path):
            iocs += ["binary"]
            targets += [path]

            # do binary similarity analysis with samples we've seen
            results = self._detect_sims(path)
            # if not results is None:
            #   return results

        # file is some compressed archive
        elif mimetypes.guess_type(path)[0] in ARCHIVE_MIME:
            iocs += ["archive"]

            # extract contents and enqueue all files for scanning
            unpacked = "unpacked_" + self.uuid
            shutil.unpack_archive(filename=path, extract_dir=unpacked)
            for dir, _, name in os.walk(unpacked):
                targets += os.path.join(dir, name)

        # file is build script, tag but won't analyze
        elif path.endswith(".sh") or path.endswith(".bat") or path.endswith(".run"):
            iocs += ["build-script"]

        # threat detection time
        for target in targets:

            """
            with open(target, "rb") as fd:
                contents = fd.read()
                iobuf = io.BytesIO(contents)
            """

            # trigger ClamAV scan first
            if scanner:
                target = os.path.abspath(target)
                logger.debug(
                    f"{self.repo_name} - Scanning {target} with ClamAV {scanner.version()}"
                )

                try:
                    results = scanner.scan(target)
                    for path, tags in results.items():
                        found, name = tags[0], tags[1]
                        if found == "FOUND":
                            iocs += [f"clamav:{name}"]
                
                # TODO: report failure for sample
                except Exception as err:
                    logger.error(f"{self.repo_name} - ClamAV exception: {err}")

            # trigger scan with VTotal if API key is supplied
            # TODO: handle rate limit exception
            if self.vt_client:
                logger.debug(f"Scanning {target} with VirusTotal client")
                analysis = self.vt_client.scan_file(contents, wait_for_completion=True)
                vtotal_mal = analysis.last_analysis_stats["malicious"]
                iocs += [f"virustotal:{vtotal_mal}"]

        # diffed file is not suspicious
        if len(iocs) == 0:
            logger.debug(f"{self.repo_name} - Nothing suspicious for {path}")
            return None

        # otherwise return hashes and indicators
        with open(path, "rb") as fd:
            contents = fd.read()

        logger.debug(f"{self.repo_name} - Malicious IOCs discovered for {path}: {iocs}")
        return {
            "sha256": hashlib.sha256(contents).hexdigest(),
            "iocs": iocs,
        }

    def _detect_sims(self, path: str):
        """
        Given a binary, generate a fuzzy hash, and query for matching items against our database.
        """
        with open(path, "rb") as fd:
            fhash = ssdeep.hash(fd.read())

        # recover attributes from fuzzy hash
        chunksize, chunk, double_chunk = fhash.split(":")
        chunksize = int(chunksize)

    def detect_suspicious(self):
        """
        Analyze an individual fork repository and detect suspicious artifacts and releases.
        """
        results = {
            # metadata needed for further processing
            "parent": self.orig_name,
            "name": self.repo_name,
            "token": self.token,
            # actually malicious indicators
            # - typosquatting: edit distance of repo name is suspiciously small
            # - commited: commmited files that is malicious
            # - releases: artifact in fork's release is malicious
            "typosquatting": False,
            "sus_committed": [],
            "sus_releases": [],
            # auxiliary: store all deltas for logging/records
            "committed": [],
            "releases": [],
        }

        logger.info(f"{self.repo_name} - checking for typosquatting")
        distance = RepoAnalysis._levenshtein_distance(
            self.fork_owner, self.parent.owner.login
        )
        if distance <= 5:
            logger.debug(f"{self.repo_name} - Typosquatting in repository name found")
            results["typosquatting"] = True

        # find commits by the fork owner and/or user known as a contributor, and
        # detect if any of the changes are new artifacts we need to analyze
        logger.info(f"{self.repo_name} - checking for suspicious commits")

        # clone repository to temporary path with random ID to prevent concurrent containers
        # from cloning to the same spot
        path = self.fork_owner + "-" + self.repo.name + "-" + self.uuid
        if os.path.exists(path):
            logger.debug(
                f"{self.repo_name} - Removing previous instance of repository on disk"
            )
            shutil.rmtree(path)

        logger.debug(f"{self.repo_name} - Cloning the repository to {path}")
        fork_repo = git.Repo.clone_from(self.repo.clone_url, path)

        logger.debug(f"{self.repo_name} - Recovering remote origins")
        origin = fork_repo.remotes.origin
        remotes = origin.pull()

        # add and sync with parent repo
        # git remote add upstream PARENT
        # git fetch upstream
        logger.debug(f"{self.repo_name} - Setting and fetching upstream remote")
        remote = fork_repo.create_remote("upstream", self.parent.clone_url)
        remote.fetch()

        # iterate over all branches, and find commits not by original contributors
        remotes = [remote.name for remote in remotes]
        for remote in remotes:

            # checkout branch in the current repo
            logger.debug(f"{self.repo_name} - Analyzing branch {remote}")
            fork_repo.git.checkout(remote)

            # check if branch exists for upstream remote, otherwise compare
            # with the default that exists, as it must be newly introduced
            branch = remote.split("/")[1]
            if not branch in self.repo_branches:
                cmp_branch = self.parent_default
            else:
                cmp_branch = branch

            # get number of commits the fork is ahead by
            # git rev-list --left-right --count origin/master...upstream/master
            logger.debug(
                f"{self.repo_name} - Checking for changes to analyze in {remote}"
            )
            count = fork_repo.git.rev_list(
                "--left-right",
                "--count",
                f"{remote}...upstream/{cmp_branch}",
            )
            ahead = int(count.split("\t")[0])
            if ahead > 0:

                # run check against files that are recently created at HEAD
                # git --no-pager diff --name-only HEAD~{AHEAD}
                head = fork_repo.head.commit
                for diff in head.diff(f"HEAD~{ahead}").iter_change_type("D"):
                    artifact = f"{path}/{diff.a_path}"

                    logger.debug(
                        f"{self.repo_name} - Analyzing `{artifact}` for suspicious indicators"
                    )
                    detected = self._analyze_artifact(artifact)
                    if detected:

                        # create object name to store in infected bucket
                        base = diff.a_path.split("/")[-1]
                        object_name = (
                            self.orig_name + "/" + self.fork_owner + "/" + base
                        )
                        self._push_to_storage(artifact, object_name)

                        # add to final report
                        detected["path"] = diff.a_path
                        results["sus_committed"] += [detected]

                    # record all changes regardless
                    results["committed"] += [diff.a_path]

        shutil.rmtree(path)

        # check if fork has releases that are not released by the original author
        logger.info(f"{self.repo_name} - checking for suspicious releases")
        for release in self.repo.get_releases():
            tag = release.tag_name
            for asset in release.get_assets():

                filename = asset.name
                url = asset.browser_download_url
                logger.debug(f"{self.repo_name} - Found asset {filename} at {url}")

                metadata = {
                    "path": filename,
                    "url": url,
                    "tag": tag,
                }

                # download file to disk
                resp = requests.get(url)
                with open(filename, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)

                logger.debug(
                    f"{self.repo_name} - Analyzing `{artifact}` for suspicious indicators"
                )
                detected = self._analyze_artifact(filename)
                if detected:

                    # create object name to store in infected bucket
                    object_name = (
                        self.orig_name + "/" + self.fork_owner + "/" + filename
                    )
                    self._push_to_storage(artifact, object_name)

                    # add to final report
                    detected.update(metadata)
                    results["sus_releases"] += [detected]

                # record all changes regardless
                results["releases"] += [metadata]
                os.remove(filename)

        self._generate_alerts(results)

    @staticmethod
    def _levenshtein_distance(str1, str2) -> int:
        """
        Helper to compute leventhestein distance between inputs to help determine typosquatting.
        """
        counter = {"+": 0, "-": 0}
        distance = 0
        for edit_code, *_ in difflib.ndiff(str1, str2):
            if edit_code == " ":
                distance += max(counter.values())
                counter = {"+": 0, "-": 0}
            else:
                counter[edit_code] += 1
        distance += max(counter.values())
        return distance

    def _push_to_storage(self, path: str, dest: str) -> None:
        """
        Helper to push artifacts to storage for cold storage and view by maintainers.
        """
        logger.info(
            f"{self.repo_name} - Pushing potentially malicious artifact to `{dest}`"
        )
        blob = bucket.blob(dest)
        blob.upload_from_filename(path)

    def _generate_alerts(self, results) -> None:
        """
        Helper to generate alerts to different sources if artifacts found are suspicious.
        """
        if (
            not results["typosquatting"]
            and len(results["sus_releases"]) == 0
            and len(results["sus_committed"]) == 0
        ):
            logger.info(
                f"{self.repo_name} - Nothing suspicious found, not publishing anymore"
            )
            return

        logger.info(f"{self.repo_name} - Outputting alerts: {results}")
        alerts = json.dumps(results).encode("utf-8")
        publisher.publish(topic, data=alerts)

    def backoff_queue(self) -> None:
        """
        Re-enqueue a repository to a seperate queue if we hit the rate limit. That one will
        push all requests back to this analyzer scheduled in the next hour. (TODO)
        """
        # msg = json.dumps(results, indent=2).encode("utf-8")
        # publisher.publish(topic, alerts)
        pass

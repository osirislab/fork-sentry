"""
repo_analysis.py
"""
import os
import logging
import shutil
import typing as t

import git
import lief
from github import Github

from google.cloud import pubsub_v1
from google.cloud import logging as cloudlogging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# setup publisher to output queue
publisher = pubsub_v1.PublisherClient()

# ensure logs can be seen by GCP
_client = cloudlogging.Client()
_handler = _client.get_default_handler()
logger.addHandler(_handler)

class RepoAnalysis:
    """
    Implements an interface for conducting fork integrity analysis across a single repository.
    """

    def __init__(self, repo_name: str, token: str, vt_token: t.Optional[str] = None):
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo_name)
        self.vt_token = vt_token

        # repo attributes
        self.orig_owner = self.repo.owner.login
        self.repo_name = self.repo.full_name
        self.default_branch = self.repo.default_branch

        self.results = {
            "alerts": {},
            "failed": {},
        }

    @staticmethod
    def push_suspicious(path) -> t.Optional[str]:
        """
        Heuristics to check if a modified file is suspicious and should be enqueued for further analysis.
        """
        # file is a binary executable/library
        if lief.is_elf(path) or lief.is_pe(path) or lief.is_macho(path):
            return "artifact"

        # file is some compressed archive
        if path.endswith("zip") or path.endswith("tar.gz") or path.endswith("tgz"):
            return "artifact"

        # file is build script
        if path.endswith(".sh") or "Makefile" in path:
            return "artifact"

        # CI/CD runner was modification
        if ".github" in path:
            return "action"

        return False

    def detect(self):
        """
        Analyze an individual fork repository and detect suspicious artifacts and releases.
        """

        logger.debug(f"Analyzing {self.repo_name}")
        suspicious = {
            "artifacts": [],
            "releases": {},
        }

        # find commits by the fork owner and/or user known as a contributor, and
        # detect if any of the changes are new artifacts we need to analyze
        logger.info("Checking for suspicious commits")

        # clone repository to temporary path
        path = self.repo.name
        if os.path.exists(path):
            shutil.rmtree(path)

        git.Git(path).clone(self.repo.clone_url)
        fork_repo = git.Repo(path)

        # iterate over all branches, and find commits not by original contributors

        # add and sync with original repo
        # git remote add upstream ORIGINAL
        # git fetch upstream
        remote = fork_repo.create_remote("upstream", self.repo.clone_url)
        remote.fetch()

        # get number of commits the fork is ahead by
        # git rev-list --left-right --count origin/master...upstream/master
        count = fork_repo.git.rev_list(
            "--left-right",
            "--count",
            f"{self.default_branch}...upstream/{self.default_branch}",
        )
        ahead = int(count.split("\t")[0])
        if ahead > 0:

            # run check against files that are recently created at HEAD
            # git --no-pager diff --name-only HEAD~{AHEAD}
            head = fork_repo.head.commit
            for diff in head.diff(f"HEAD~{ahead}").iter_change_type("D"):
                artifact = f"{path}/{diff.a_path}"
                suspicious["artifacts"] += [artifact]

        shutil.rmtree(path)

        # check if fork has releases that are not released by the original author
        logger.info("Checking for suspicious releases")
        for release in self.repo.get_releases():
            tag = release.tag_name

            suspicious["releases"][tag] = []
            for asset in release.get_assets():
                suspicious["releases"][tag] += [
                    {
                        "name": asset.name,
                        "url": asset.browser_download_url,
                    }
                ]
                logger.debug(f"{asset.name}: {asset.browser_download_url}")

        return suspicious

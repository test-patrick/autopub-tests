from __future__ import annotations

import os
import json
import pathlib
from github import Github
from autopub.exceptions import AutopubException
from autopub.types import ReleaseInfo
from github import Auth

from autopub.plugins import AutopubPlugin


class GithubPlugin(AutopubPlugin):
    @property
    def github(self) -> Github:
        auth = Auth.Token(os.environ["GITHUB_TOKEN"])

        return Github(auth=auth)

    @property
    def event(self):
        path = os.environ["GITHUB_EVENT_PATH"]

        return json.loads(pathlib.Path(path).read_text())

    def on_release_notes_invalid(self, exception: AutopubException):
        self._send_comment("Release notes are invalid", exception.message)

    def on_release_notes_valid(self, release_info: ReleaseInfo):
        # TODO: print release info
        self._send_comment("Release notes are valid", "Good job!")

    def _send_comment(self, title: str, body: str):
        repo = self.github.get_repo(self.event["repository"]["full_name"])
        pr = repo.get_pull(self.event["pull_request"]["number"])

        pr.create_issue_comment(f"## {title}\n\n{body}")

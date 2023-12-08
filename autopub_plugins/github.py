from __future__ import annotations

import os
import json
import pathlib
from github import Github
from autopub.exceptions import AutopubException
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
        print(self.event)

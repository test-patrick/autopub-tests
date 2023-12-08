from __future__ import annotations

import os
import json
import pathlib
import functools
from github import Github
from autopub.exceptions import AutopubException
from autopub.types import ReleaseInfo
from github import Auth
import textwrap
from autopub.plugins import AutopubPlugin


class GithubPlugin(AutopubPlugin):
    @property
    def github(self) -> Github:
        auth = Auth.Token(os.environ["GITHUB_TOKEN"])

        return Github(auth=auth)

    @functools.cached_property
    def event(self):
        path = os.environ["GITHUB_EVENT_PATH"]

        return json.loads(pathlib.Path(path).read_text())

    @property
    def is_pr(self) -> bool:
        return self.event.get("pull_request") is not None

    def on_release_notes_invalid(self, exception: AutopubException):
        if not self.is_pr:
            return

        text = textwrap.dedent(
            f"""
            Your release notes are invalid. Please fix them and try again.

            The following error was raised:

            ```
            {exception}
            ```
            """
        ).strip()

        self._send_comment(text)

    def on_release_notes_valid(self, release_info: ReleaseInfo):
        if not self.is_pr:
            return

        text = textwrap.dedent(
            f"""
            Your release notes look good!

            ## Release Info

            - **Version:** {release_info.version}
            - **Release type:** {release_info.release_type}

            ## Release Notes
            """
        ).strip()

        text += "\n\n" + release_info.release_notes

        self._send_comment(text)

    def _send_comment(self, body: str):
        repo = self.github.get_repo(self.event["repository"]["full_name"])
        pr = repo.get_pull(self.event["pull_request"]["number"])

        comment_signature = "<!-- autopub-release-check ✨ -->"

        message = f"{body}\n\n{comment_signature}"

        for comment in pr.get_issue_comments():
            if comment.body.endswith(comment_signature):
                comment.edit(message)
                return

        pr.create_issue_comment(message)

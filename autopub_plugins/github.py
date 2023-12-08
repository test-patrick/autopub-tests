from __future__ import annotations

import os
import httpx
import json
import pathlib
import functools
from typing import Any
from github import Github
from github.Repository import Repository
from autopub.exceptions import AutopubException
from autopub.types import ReleaseInfo
from github import Auth
import textwrap
from autopub.plugins import AutopubPlugin


def _get_pull_request_from_sha(repo: Repository, sha: str):
    endpoint = f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/commits/{sha}/pulls"

    headers = {
        "Authorization": f"token {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github.groot-preview+json",
    }
    response = httpx.get(endpoint, headers=headers)

    response.raise_for_status()
    pulls = response.json()

    assert len(pulls) == 1

    return pulls[0]


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

    @functools.cached_property
    def pr(self) -> dict[str, Any] | None:
        if not self.is_pr:
            return None

        repo = self.github.get_repo(self.event["repository"]["full_name"])

        return _get_pull_request_from_sha(repo, sha=os.environ["GITHUB_SHA"])

    @property
    def additional_message(self) -> str | None:
        if not self.pr:
            return None

        user = self.pr["user"]["login"]
        number = self.pr["number"]

        return f"This release was contributed by @{user} in PR #{number}."

    def prepare(self, release_info: ReleaseInfo) -> None:
        if self.additional_message is not None:
            release_info.additional_release_notes.append(self.additional_message)

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

    def post_publish(self, release_info: ReleaseInfo):
        repo = self.github.get_repo(self.event["repository"]["full_name"])

        version = release_info.version

        assert version is not None

        message = release_info.release_notes

        if self.additional_message is not None:
            message += "\n\n" + self.additional_message

        repo.create_git_release(
            tag=version,
            name=version,
            message=message,
            draft=False,
            prerelease=False,
        )

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

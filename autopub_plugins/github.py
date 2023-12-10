from __future__ import annotations

import os
import httpx
import json
import pathlib
import functools
from typing import Any
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository
from typing import Set
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

    @property
    def repo(self) -> Repository:
        return self.github.get_repo(self.event["repository"]["full_name"])

    @functools.cached_property
    def source_pr(self) -> dict[str, Any] | None:
        repo = self.github.get_repo(self.event["repository"]["full_name"])

        return _get_pull_request_from_sha(repo, sha=os.environ["GITHUB_SHA"])

    def _join_with_oxford_commas(self, items: list[str]) -> str:
        if len(items) == 1:
            return items[0]

        if len(items) == 2:
            return f"{items[0]} and {items[1]}"

        return f"{', '.join(items[:-1])}, and {items[-1]}"

    def _get_contributors(self, pull_request: PullRequest) -> list[str]:
        contributors_set: Set[str] = set()

        commits = pull_request.get_commits()

        for commit in commits:
            if commit.author.login == pull_request.user.login:
                continue

            contributors_set.add(commit.author.login)

        reviews = pull_request.get_reviews()

        for review in reviews:
            contributors_set.add(review.user.login)

        return [pull_request.user.login] + sorted(contributors_set)

    def _get_reviewers(self, pull_request: PullRequest) -> list[str]:
        reviewers_set: Set[str] = set()

        reviews = pull_request.get_reviews()

        for review in reviews:
            reviewers_set.add(review.user.login)

        return sorted(reviewers_set)

    def get_additional_message(self, with_links: bool = False) -> str | None:
        if not self.source_pr:
            return None

        pr = self.repo.get_pull(self.source_pr["number"])

        def _get_user_link(user: str) -> str:
            return f"[@{user}](https://github.com/{user})"

        if with_links:
            number = f"[#{pr.number}]({pr.html_url})"
            contributors = self._join_with_oxford_commas(
                [_get_user_link(user) for user in self._get_contributors(pr)]
            )
            reviewers = self._join_with_oxford_commas(
                [_get_user_link(user) for user in self._get_reviewers(pr)]
            )

        else:
            reviewers = self._join_with_oxford_commas(self._get_reviewers(pr))
            contributors = self._join_with_oxford_commas(self._get_contributors(pr))
            number = f"#{pr.number}"

        return (
            f"This release was contributed by {contributors} in PR {number}.\n"
            f"Thanks to {reviewers} for reviewing!"
        )

    def prepare(self, release_info: ReleaseInfo) -> None:
        additional_message = self.get_additional_message(with_links=True)

        if additional_message is not None:
            release_info.additional_release_notes.append(additional_message)

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
        version = release_info.version

        assert version is not None

        message = release_info.release_notes

        additional_message = self.get_additional_message()

        if additional_message is not None:
            message += "\n\n" + additional_message

        release = self.repo.create_git_release(
            tag=version,
            name=version,
            message=message,
            draft=False,
            prerelease=False,
        )

        if self.source_pr:
            pr = self.repo.get_pull(self.source_pr["number"])

            release_url = f"[{release.title}]({release.html_url})"

            pr.create_issue_comment(f"🎉 This PR was included in {release_url} 🎉")

    def _send_comment(self, body: str):
        pr = self.repo.get_pull(self.event["pull_request"]["number"])

        comment_signature = "<!-- autopub-release-check ✨ -->"

        message = f"{body}\n\n{comment_signature}"

        for comment in pr.get_issue_comments():
            if comment.body.endswith(comment_signature):
                comment.edit(message)
                return

        pr.create_issue_comment(message)

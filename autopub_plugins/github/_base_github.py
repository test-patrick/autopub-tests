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
from github import Auth
from autopub.plugins import AutopubPlugin


def join_with_oxford_commas(items: list[str], prefix: str = "") -> str:
    items = [f"{prefix}{item}" for item in items]

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return f"{items[0]} and {items[1]}"

    return f"{', '.join(items[:-1])}, and {items[-1]}"


def get_pull_request_from_sha(repo: Repository, sha: str):
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


class BaseGithubPlugin(AutopubPlugin):
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

        return get_pull_request_from_sha(repo, sha=os.environ["GITHUB_SHA"])

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

    def _get_user_link(self, user: str) -> str:
        return f"[@{user}](https://github.com/{user})"

    def _get_reviews_message(
        self, pr: PullRequest, with_links: bool = False
    ) -> str | None:
        reviewers = self._get_reviewers(pr)

        if not reviewers:
            return None

        if with_links:
            reviewers_text = join_with_oxford_commas(
                [self._get_user_link(user) for user in reviewers]
            )
        else:
            reviewers_text = join_with_oxford_commas(reviewers, prefix="@")

        return f"Thanks to {reviewers_text} for reviewing!"

    def get_additional_message(self, with_links: bool = False) -> str | None:
        if not self.source_pr:
            return None

        pr = self.repo.get_pull(self.source_pr["number"])

        contributors = self._get_contributors(pr)

        if with_links:
            number_text = f"[#{pr.number}]({pr.html_url})"
            contributors_text = join_with_oxford_commas(
                [self._get_user_link(user) for user in contributors]
            )

        else:
            contributors_text = join_with_oxford_commas(contributors, prefix="@")
            number_text = f"#{pr.number}"

        reviews_text = self._get_reviews_message(pr, with_links=with_links)

        return (
            f"This release was contributed by {contributors_text} in PR {number_text}.\n"
            f"{reviews_text or ''}"
        ).strip()

    def _send_comment(self, body: str):
        pr = self.repo.get_pull(self.event["pull_request"]["number"])

        comment_signature = "<!-- autopub-release-check ✨ -->"

        message = f"{body}\n\n{comment_signature}"

        for comment in pr.get_issue_comments():
            if comment.body.endswith(comment_signature):
                comment.edit(message)
                return

        pr.create_issue_comment(message)

from __future__ import annotations

from autopub.exceptions import AutopubException
from autopub.types import ReleaseInfo
import textwrap
from autopub.plugins import AutopubPlugin
import string

from github.IssueComment import IssueComment

from ._base_github import BaseGithubPlugin


class GithubPRCommentPlugin(BaseGithubPlugin, AutopubPlugin):
    comment_signature = "<!-- autopub-release-check ✨ -->"

    # TODO: should we show an example of a valid release?
    invalid_release_template = string.Template(
        textwrap.dedent(
            """
            Your release notes are invalid. Please fix them and try again.

            The following error was raised:

            ```
            $exception
            ```
            """
        ).strip()
    )

    valid_release_template = string.Template(
        textwrap.dedent(
            """
            Your release notes look good!

            ## Release Info

            - **Version:** $version
            - **Release type:** $release_type

            ## Release Notes

            $release_notes
            """
        ).strip()
    )

    def on_release_notes_invalid(self, exception: AutopubException):
        if not self.is_pr:
            return

        text = self.invalid_release_template.substitute(exception=str(exception))

        self._send_comment(text)

    def on_release_notes_valid(self, release_info: ReleaseInfo):
        if not self.is_pr:
            return

        text = self.valid_release_template.substitute(
            version=release_info.version,
            release_type=release_info.release_type,
            release_notes=release_info.release_notes,
        )

        self._send_comment(text)

    def _find_previous_comment(self) -> IssueComment | None:
        pr = self.repo.get_pull(self.event["pull_request"]["number"])

        for comment in pr.get_issue_comments():
            if comment.body.endswith(self.comment_signature):
                return comment

        return None

    def _send_comment(self, body: str):
        pr = self.repo.get_pull(self.event["pull_request"]["number"])

        message = f"{body}\n\n{self.comment_signature}"

        if previous_comment := self._find_previous_comment():
            previous_comment.edit(message)

            return

        pr.create_issue_comment(message)


__all__ = ["GithubPRCommentPlugin"]

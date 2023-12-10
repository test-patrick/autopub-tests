from __future__ import annotations

from autopub.types import ReleaseInfo
from autopub.plugins import AutopubPlugin

from ._base_github import BaseGithubPlugin


class GithubReleasePlugin(BaseGithubPlugin, AutopubPlugin):
    # TODO: this is used for the changelog, maybe move somewhere else?
    def prepare(self, release_info: ReleaseInfo) -> None:
        additional_message = self.get_additional_message(with_links=True)

        if additional_message is not None:
            print("appending additional message", additional_message)
            release_info.additional_release_notes.append(additional_message)

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


__all__ = ["GithubReleasePlugin"]

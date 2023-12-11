from __future__ import annotations

from autopub.types import ReleaseInfo
from autopub.plugins import AutopubPlugin
import string
import textwrap

from ._base_github import BaseGithubPlugin


BOTS = [
    "dependabot-preview[bot]",
    "dependabot-preview",
    "dependabot",
    "dependabot[bot]",
]


class GithubInviteContributorPlugin(BaseGithubPlugin, AutopubPlugin):
    organisation = "test-patrick"
    team_slug = "people"

    invite_template = string.Template(
        textwrap.dedent(
            """
            Hi @{user},

            Thanks for your contribution to Strawberry 🍓!

            We'd like to invite you to join the Strawberry Organisation on GitHub,
            please check your email for an invitation 😊

            ...
            """
        ).strip()
    )

    def post_publish(self, release_info: ReleaseInfo):
        if not self.source_pr:
            return

        user = self.source_pr.user

        if user.login in BOTS:
            return

        organisation = self.github.get_organization(self.organisation)
        team = organisation.get_team_by_slug(self.team_slug)

        if team.has_in_members(user):
            return

        team.add_membership(user)

        text = self.invite_template.substitute(user=user.login)

        self.source_pr.create_issue_comment(text)


__all__ = ["GithubInviteContributorPlugin"]

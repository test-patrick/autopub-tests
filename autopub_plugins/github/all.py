from .invite_contributor import GithubInviteContributorPlugin
from .pr_comment import GithubPRCommentPlugin
from .release import GithubReleasePlugin


class GithubPlugin(
    GithubInviteContributorPlugin, GithubPRCommentPlugin, GithubReleasePlugin
):
    pass


__all__ = ["GithubPlugin"]

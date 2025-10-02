"""Minimal GitHub API helper for updating deploy comments."""

from __future__ import annotations

from typing import Optional

import requests


class GithubCommentError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


def _headers(token: str) -> dict[str, str]:
    if not token:
        raise ValueError("GitHub token is required")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-actions-deploy/0.1.0",
    }


def upsert_pull_request_comment(
    *,
    token: str,
    repo: str,
    pr_number: int,
    marker: str,
    body: str,
    api_url: str = "https://api.github.com",
) -> int:
    """Create or update the deployment status comment on the pull request."""

    if not repo:
        raise ValueError("repo is required")
    if pr_number <= 0:
        raise ValueError("pr_number must be positive")

    session = requests.Session()
    comments_url = f"{api_url}/repos/{repo}/issues/{pr_number}/comments"

    # Find an existing comment containing the marker.
    next_url: Optional[str] = comments_url
    headers = _headers(token)
    comment_id: Optional[int] = None
    while next_url:
        response = session.get(next_url, headers=headers, timeout=30)
        if response.status_code >= 400:
            raise GithubCommentError(f"Failed to list PR comments: {response.status_code} {response.text}")
        for comment in response.json():
            if marker in comment.get("body", ""):
                comment_id = int(comment["id"])
                break
        next_url = None
        if "next" in response.links:
            next_url = response.links["next"]["url"]
        if comment_id is not None:
            break

    if comment_id is not None:
        patch_url = f"{comments_url}/{comment_id}"
        response = session.patch(patch_url, headers=headers, json={"body": body}, timeout=30)
        if response.status_code >= 400:
            raise GithubCommentError(
                f"Failed to update PR comment {comment_id}: {response.status_code} {response.text}"
            )
        return comment_id

    response = session.post(comments_url, headers=headers, json={"body": body}, timeout=30)
    if response.status_code >= 400:
        raise GithubCommentError(f"Failed to create PR comment: {response.status_code} {response.text}")
    return int(response.json()["id"])


__all__ = ["GithubCommentError", "upsert_pull_request_comment"]

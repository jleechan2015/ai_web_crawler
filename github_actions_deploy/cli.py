"""Command line entrypoint for the GitHub Actions deploy helper."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

from .async_build import AsyncBuildClient, AsyncBuildError, BuildStatus
from .github import upsert_pull_request_comment
from .pr_comments import COMMENT_MARKER, IndicatorState, ProgressIndicator, render_progress_comment


class ConfigurationError(RuntimeError):
    """Raised when CLI configuration is invalid."""


def _parse_key_value(items: Optional[Sequence[str]]) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    if not items:
        return results
    for item in items:
        if "=" not in item:
            raise argparse.ArgumentTypeError(f"Expected KEY=VALUE format, got {item!r}")
        key, value = item.split("=", 1)
        results.append((key.strip(), value.strip()))
    return results


def _indicator_from_build(status: BuildStatus, *, preview_urls: Sequence[Tuple[str, str]]) -> List[ProgressIndicator]:
    build_indicator_state = {
        BuildStatus.QUEUED: IndicatorState.PENDING,
        BuildStatus.RUNNING: IndicatorState.RUNNING,
        BuildStatus.SUCCEEDED: IndicatorState.SUCCESS,
        BuildStatus.FAILED: IndicatorState.FAILED,
        BuildStatus.CANCELLED: IndicatorState.FAILED,
    }[status]

    indicators = [
        ProgressIndicator(
            name="Async build",
            state=build_indicator_state,
            url=None,
            description="Triggered through VPC-SC safe endpoint",
        )
    ]

    preview_state = IndicatorState.PENDING
    if preview_urls and status == BuildStatus.SUCCEEDED:
        preview_state = IndicatorState.SUCCESS
    elif status in {BuildStatus.FAILED, BuildStatus.CANCELLED}:
        preview_state = IndicatorState.FAILED

    if preview_urls:
        preview_url = preview_urls[0][1]
        extra_links = [f"[{label}]({url})" for label, url in preview_urls[1:]]
        preview_description: Optional[str] = None
        if extra_links:
            preview_description = "Additional previews:<br />" + "<br />".join(extra_links)
    else:
        preview_url = None
        preview_description = "Provisioning preview service"

    indicators.append(
        ProgressIndicator(
            name="Preview service",
            state=preview_state,
            url=preview_url,
            description=preview_description,
        )
    )

    return indicators


def _write_outputs(outputs: Dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in outputs.items():
            handle.write(f"{key}={value}\n")


def _load_payload(payload: Optional[str]) -> Dict[str, object]:
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"Invalid JSON payload: {error}") from error


def _resolve_base_url(provided: Optional[str]) -> str:
    candidate = (provided or os.environ.get("ASYNC_BUILD_BASE_URL") or "").strip()
    if not candidate:
        raise ConfigurationError(
            "Async build base URL is required. Provide --base-url or set the ASYNC_BUILD_BASE_URL secret."
        )
    return candidate


def _upsert_comment(
    *,
    token: str,
    repo: str,
    pr_number: int,
    body: str,
) -> int:
    return upsert_pull_request_comment(
        token=token,
        repo=repo,
        pr_number=pr_number,
        marker=COMMENT_MARKER,
        body=body,
    )


def cmd_start(args: argparse.Namespace) -> int:
    base_url = _resolve_base_url(args.base_url)

    client = AsyncBuildClient(
        base_url,
        token=args.build_token,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )
    payload = _load_payload(args.payload)
    build = client.start_build(payload)

    preview_links = _parse_key_value(args.preview_url)
    quick_links = _parse_key_value(args.quick_link)
    indicators = _indicator_from_build(build.status, preview_urls=preview_links)

    body = render_progress_comment(
        build=build,
        indicators=indicators,
        quick_links=quick_links,
        header=args.header,
    )

    comment_id = _upsert_comment(
        token=args.github_token,
        repo=args.repo,
        pr_number=args.pr_number,
        body=body,
    )

    outputs = {
        "build_id": build.build_id,
        "comment_id": str(comment_id),
        "build_status": build.status.value,
    }
    if preview_links:
        outputs["preview_url"] = preview_links[0][1]
        outputs["preview_urls"] = json.dumps(preview_links)
    _write_outputs(outputs)

    return 0


def cmd_poll(args: argparse.Namespace) -> int:
    base_url = _resolve_base_url(args.base_url)

    client = AsyncBuildClient(
        base_url,
        token=args.build_token,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )

    preview_links = _parse_key_value(args.preview_url)
    quick_links = _parse_key_value(args.quick_link)

    try:
        build = client.wait_for_completion(
            args.build_id,
            timeout=args.wait_timeout,
            poll_interval=args.poll_interval,
        )
        status = build.status
    except AsyncBuildError:
        # Fetch final status to display detailed error message.
        build = client.get_build(args.build_id)
        status = build.status
        if status not in {BuildStatus.SUCCEEDED, BuildStatus.FAILED, BuildStatus.CANCELLED}:
            status = BuildStatus.FAILED
        build = replace(build, status=status)
        result_code = 1
    else:
        result_code = 0 if status == BuildStatus.SUCCEEDED else 1

    indicators = _indicator_from_build(status, preview_urls=preview_links)

    body = render_progress_comment(
        build=build,
        indicators=indicators,
        quick_links=quick_links,
        header=args.header,
    )

    _upsert_comment(
        token=args.github_token,
        repo=args.repo,
        pr_number=args.pr_number,
        body=body,
    )

    outputs = {
        "build_status": status.value,
    }
    if preview_links:
        outputs["preview_url"] = preview_links[0][1]
        outputs["preview_urls"] = json.dumps(preview_links)
    _write_outputs(outputs)

    return result_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub Actions deploy helper")
    parser.add_argument("--header", default="🚀 Deploy Preview", help="Heading displayed in the PR comment")
    parser.add_argument("--repo", required=True, help="GitHub repository in owner/name format")
    parser.add_argument("--pr-number", type=int, required=True, help="Pull request number")
    parser.add_argument("--github-token", required=True, help="Token with permission to manage PR comments")
    parser.add_argument("--base-url", help="Base URL of the async build service")
    parser.add_argument("--build-token", help="Bearer token for the build service")
    parser.add_argument("--payload", help="JSON payload describing the build request")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout for build API calls")
    parser.add_argument("--poll-interval", type=float, default=10.0, help="Polling frequency for build status")
    parser.add_argument(
        "--preview-url",
        action="append",
        help="Preview label and URL (format: Label=https://...)",
    )
    parser.add_argument(
        "--quick-link",
        action="append",
        help="Additional quick link (format: Label=https://...)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    start_parser = subparsers.add_parser("start", help="Trigger the async build and post a starting comment")
    start_parser.set_defaults(func=cmd_start)

    poll_parser = subparsers.add_parser("poll", help="Wait for build completion and update the comment")
    poll_parser.add_argument("--build-id", required=True, help="Identifier returned from the start command")
    poll_parser.add_argument(
        "--wait-timeout",
        type=float,
        default=3600.0,
        help="Maximum time (seconds) to wait for build completion",
    )
    poll_parser.set_defaults(func=cmd_poll)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigurationError as error:
        parser.error(str(error))
        return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

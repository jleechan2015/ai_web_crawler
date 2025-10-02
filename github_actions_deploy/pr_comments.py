"""Helpers for rendering professional pull request deployment comments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple

from .async_build import BuildInfo, BuildStatus

COMMENT_MARKER = "<!-- github-actions-deploy -->"


class IndicatorState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

    @property
    def icon(self) -> str:
        return {
            IndicatorState.PENDING: "🕒",
            IndicatorState.RUNNING: "🚧",
            IndicatorState.SUCCESS: "✅",
            IndicatorState.FAILED: "❌",
        }[self]

    @property
    def label(self) -> str:
        return {
            IndicatorState.PENDING: "Pending",
            IndicatorState.RUNNING: "In progress",
            IndicatorState.SUCCESS: "Ready",
            IndicatorState.FAILED: "Failed",
        }[self]


@dataclass(frozen=True)
class ProgressIndicator:
    """Represents a single row in the deploy status table."""

    name: str
    state: IndicatorState
    url: Optional[str] = None
    description: Optional[str] = None

    def render_row(self) -> str:
        status = f"{self.state.icon} {self.state.label}"
        link = f"[Open]({self.url})" if self.url else "—"
        note = f"<br />{self.description}" if self.description else ""
        return f"| **{self.name}** | {status}{note} | {link} |"


def _format_quick_links(links: Sequence[Tuple[str, str]]) -> str:
    if not links:
        return ""
    rendered = " ".join(f"[`{label}`]({url})" for label, url in links)
    return f"\n**Quick links:** {rendered}\n"


def render_progress_comment(
    *,
    build: BuildInfo,
    indicators: Iterable[ProgressIndicator],
    quick_links: Sequence[Tuple[str, str]] | None = None,
    header: str = "🚀 Deploy Preview",
    footer: Optional[str] = None,
) -> str:
    """Render the markdown comment body for the current deploy status."""

    indicators_list: List[ProgressIndicator] = list(indicators)
    if not indicators_list:
        raise ValueError("At least one progress indicator is required")

    table_rows = "\n".join(indicator.render_row() for indicator in indicators_list)
    table = "| Stage | Status | Link |\n| --- | --- | --- |\n" + table_rows

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    quick_links_block = _format_quick_links(quick_links or [])

    final_footer = footer or ""
    if build.logs_url and "Logs" not in {label for label, _ in (quick_links or [])}:
        final_footer += f"\n🔍 [View logs]({build.logs_url})"
    if build.detail_url:
        final_footer += f"\n📦 [Build details]({build.detail_url})"
    final_footer = final_footer.strip()

    if final_footer:
        final_footer = f"\n\n{final_footer}"

    banner = "" if build.status == BuildStatus.SUCCEEDED else ""
    if build.status == BuildStatus.FAILED:
        banner = "\n> **Deployment failed.** Please review the logs linked below."
    elif build.status == BuildStatus.CANCELLED:
        banner = "\n> **Deployment cancelled.** Trigger a new run if needed."

    body = (
        f"{COMMENT_MARKER}\n"
        f"## {header}\n\n"
        f"Build **{build.build_id}** is currently **{build.status.value}**.{banner}\n\n"
        f"{table}\n"
        f"{quick_links_block}"
        f"_Last updated: {timestamp}_"
        f"{final_footer}\n"
    )
    return body


__all__ = [
    "COMMENT_MARKER",
    "IndicatorState",
    "ProgressIndicator",
    "render_progress_comment",
]

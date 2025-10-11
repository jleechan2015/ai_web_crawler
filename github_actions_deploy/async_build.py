"""Async build orchestration helpers.

These utilities allow GitHub Actions workflows to trigger remote builds that run
inside VPC Service Controls or other restricted environments where streaming
logs are blocked. Instead of tailing the build output, the client only performs
short polling against metadata endpoints, pulling the final logs once the build
finishes.
"""

from __future__ import annotations

import enum
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional

import requests


class AsyncBuildError(RuntimeError):
    """Raised when an asynchronous build fails or cannot be queried."""


class BuildStatus(str, enum.Enum):
    """Represents the canonical set of build states."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {self.SUCCEEDED, self.FAILED, self.CANCELLED}

    @classmethod
    def from_remote(cls, value: str) -> "BuildStatus":
        """Map an arbitrary remote status string to the canonical enum."""

        normalized = value.upper()
        if normalized in cls.__members__:
            return cls[normalized]
        if normalized in {"SUCCESS", "FINISHED"}:
            return cls.SUCCEEDED
        if normalized in {"ERROR", "FAILURE"}:
            return cls.FAILED
        if normalized in {"CANCEL", "CANCELED"}:
            return cls.CANCELLED
        if normalized in {"PENDING", "SCHEDULED"}:
            return cls.QUEUED
        return cls.RUNNING


@dataclass(slots=True)
class BuildInfo:
    """Metadata returned by the async build service."""

    build_id: str
    status: BuildStatus
    detail_url: Optional[str] = None
    logs_url: Optional[str] = None
    metadata: MutableMapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "build_id": self.build_id,
            "status": self.status.value,
            "detail_url": self.detail_url,
            "logs_url": self.logs_url,
            "metadata": dict(self.metadata),
        }


class AsyncBuildClient:
    """Client for triggering and polling asynchronous builds."""

    def __init__(
        self,
        base_url: str,
        *,
        token: Optional[str] = None,
        timeout: float = 30.0,
        poll_interval: float = 10.0,
        session: Optional[requests.Session] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if not base_url:
            raise ValueError("base_url is required")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.session = session or requests.Session()
        self.logger = logger or logging.getLogger(__name__)
        self._headers: Dict[str, str] = {"Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    # Public API -----------------------------------------------------------------
    def start_build(self, payload: Mapping[str, Any]) -> BuildInfo:
        """Trigger a new build and return its metadata."""

        url = f"{self.base_url}/builds"
        self.logger.debug("Starting async build via %s", url)
        response = self.session.post(url, json=payload, timeout=self.timeout, headers=self._headers)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:  # pragma: no cover - thin wrapper
            raise AsyncBuildError(f"Failed to start build: {error}") from error

        data = response.json()
        build = self._parse_build(data)
        self.logger.info("Async build %s started with status %s", build.build_id, build.status.value)
        return build

    def get_build(self, build_id: str) -> BuildInfo:
        """Fetch build metadata by identifier."""

        url = f"{self.base_url}/builds/{build_id}"
        self.logger.debug("Fetching async build state from %s", url)
        response = self.session.get(url, timeout=self.timeout, headers=self._headers)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:  # pragma: no cover - thin wrapper
            raise AsyncBuildError(f"Failed to fetch build {build_id}: {error}") from error

        data = response.json()
        build = self._parse_build(data)
        self.logger.debug("Build %s currently %s", build.build_id, build.status.value)
        return build

    def wait_for_completion(
        self,
        build_id: str,
        *,
        timeout: float | None = None,
        poll_interval: float | None = None,
    ) -> BuildInfo:
        """Poll until the build reaches a terminal state."""

        poll_interval = poll_interval or self.poll_interval
        deadline = time.monotonic() + (timeout or 3600)

        last_status: Optional[BuildStatus] = None
        while True:
            build = self.get_build(build_id)
            if build.status != last_status:
                self.logger.info("Build %s transitioned to %s", build.build_id, build.status.value)
                last_status = build.status

            if build.status.is_terminal:
                if build.status == BuildStatus.SUCCEEDED:
                    return build
                raise AsyncBuildError(f"Build {build_id} completed with status {build.status.value}")

            if time.monotonic() > deadline:
                raise AsyncBuildError(f"Timed out waiting for build {build_id}")

            time.sleep(poll_interval)

    # Internal helpers ------------------------------------------------------------
    def _parse_build(self, data: Mapping[str, Any]) -> BuildInfo:
        try:
            build_id = str(data["id"])
        except KeyError as error:  # pragma: no cover - defensive
            raise AsyncBuildError("Build response missing 'id'") from error

        status_value = str(data.get("status", "RUNNING"))
        detail_url = data.get("detail_url") or data.get("html_url")
        logs_url = data.get("logs_url") or data.get("log_url")
        metadata = self._extract_metadata(data.get("metadata"))

        return BuildInfo(
            build_id=build_id,
            status=BuildStatus.from_remote(status_value),
            detail_url=detail_url,
            logs_url=logs_url,
            metadata=metadata,
        )

    def _extract_metadata(self, metadata: Any) -> MutableMapping[str, Any]:
        if metadata is None:
            return {}
        if isinstance(metadata, MutableMapping):
            return dict(metadata)
        if isinstance(metadata, Mapping):
            return dict(metadata)
        if isinstance(metadata, Iterable):
            return {str(idx): value for idx, value in enumerate(metadata)}
        return {"value": metadata}


__all__ = [
    "AsyncBuildClient",
    "AsyncBuildError",
    "BuildInfo",
    "BuildStatus",
]

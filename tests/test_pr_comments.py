from github_actions_deploy.async_build import BuildInfo, BuildStatus
from github_actions_deploy.pr_comments import IndicatorState, ProgressIndicator, render_progress_comment


def test_render_progress_comment_success():
    build = BuildInfo(
        build_id="build-123",
        status=BuildStatus.SUCCEEDED,
        detail_url="https://example.com/build/123",
        logs_url="https://example.com/build/123/logs",
    )
    indicators = [
        ProgressIndicator(name="Async build", state=IndicatorState.SUCCESS, url="https://example.com/build/123"),
        ProgressIndicator(name="Preview service", state=IndicatorState.SUCCESS, url="https://example.com/preview"),
    ]
    comment = render_progress_comment(
        build=build,
        indicators=indicators,
        quick_links=[
            ("Preview", "https://example.com/preview"),
            ("Logs", "https://example.com/build/123/logs"),
        ],
    )

    assert "build-123" in comment
    assert "Deploy Preview" in comment
    assert "✅ Ready" in comment
    assert "Quick links" in comment
    assert "View logs" not in comment  # quick link already points to logs


def test_render_progress_comment_failure_includes_banner():
    build = BuildInfo(
        build_id="build-456",
        status=BuildStatus.FAILED,
        detail_url="https://example.com/build/456",
        logs_url="https://example.com/build/456/logs",
    )
    indicators = [
        ProgressIndicator(name="Async build", state=IndicatorState.FAILED),
    ]
    comment = render_progress_comment(build=build, indicators=indicators)

    assert "Deployment failed" in comment
    assert "build-456" in comment
    assert "View logs" in comment

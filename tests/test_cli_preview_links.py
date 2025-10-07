from github_actions_deploy.async_build import BuildInfo, BuildStatus
from github_actions_deploy.cli import _merge_preview_links, _metadata_preview_links


def _build(metadata):
    return BuildInfo(build_id="build", status=BuildStatus.RUNNING, metadata=metadata)


def test_metadata_preview_links_accepts_string():
    build = _build({"preview_url": "https://preview.example.com"})
    links = _metadata_preview_links(build.metadata)
    assert links == [("Preview", "https://preview.example.com")]


def test_metadata_preview_links_handles_structured_values():
    metadata = {
        "preview_links": [
            {"label": "App", "url": "https://app.example.com"},
            {"name": "Docs", "href": "https://docs.example.com"},
        ],
    }
    build = _build(metadata)
    links = _metadata_preview_links(build.metadata)
    assert links == [
        ("App", "https://app.example.com"),
        ("Docs", "https://docs.example.com"),
    ]


def test_merge_preview_links_prioritises_cli_and_deduplicates():
    cli_links = [("Manual", "https://preview.example.com")]
    metadata_links = [("Preview", "https://preview.example.com"), ("Docs", "https://docs.example.com")]

    merged = _merge_preview_links(cli_links, metadata_links)

    assert merged == [
        ("Manual", "https://preview.example.com"),
        ("Docs", "https://docs.example.com"),
    ]

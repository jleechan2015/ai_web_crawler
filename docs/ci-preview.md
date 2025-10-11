# Deploy previews in restricted networks

This repository includes a GitHub Actions workflow and reusable utilities that provide asynchronous deployment previews even when
traditional log streaming is blocked by VPC Service Controls. The solution is composed of the following pieces:

1. **`github-actions-deploy` Python package** – ships in this repository and can be published to PyPI for reuse. It provides an
   `AsyncBuildClient` that interacts with a remote build service in a fire-and-forget fashion, then polls for completion to avoid
   streaming logs across network boundaries.
2. **`pr-dev-preview.yml` workflow** – triggers on pull request activity, kicks off the async build, and posts professional status
   updates back to the PR. Because the workflow never tails logs directly, it works inside VPC-SC environments where log streaming
   is disallowed. A follow-up MCP smoke test job validates the packaged server still boots successfully once the preview build
   passes.
3. **Rich pull request comments** – every run posts an actionable comment with build progress, quick access links, and preview
   URLs. The comment is updated in-place so reviewers always have the latest status.

## Prerequisites

* A remote build API that supports asynchronous build start + status polling (for example, Cloud Build or a custom internal
  service). The workflow expects JSON responses with `id`, `status`, and optional `detail_url`/`logs_url` fields.
* A GitHub App or classic personal access token stored in `GH_DEPLOY_TOKEN` with permission to read and write PR comments.
* Secrets for your build service endpoint and any authentication values.

## Configuration steps

1. Copy `.github/workflows/pr-dev-preview.yml` into your repository (it is already committed here).
2. Configure secrets in the repository or organization:
   * `GH_DEPLOY_TOKEN` – GitHub token for comment updates.
   * `ASYNC_BUILD_BASE_URL` – Base URL for the async build service (e.g. `https://cloudbuild.googleapis.com/v1/projects/...`).
   * `ASYNC_BUILD_TOKEN` – Optional bearer token for the build service. Leave unset when not required.
   * `PREVIEW_SERVICE_URL` – (Optional) When the build produces a public preview, supply the URL so it can be surfaced in PR
     comments.
3. Adjust the payload passed in the `Start async build` step to match your build API. The default example submits a JSON body with
   `source`, `substitutions`, and `tags` keys commonly used by GCP Cloud Build.
4. Commit the workflow and package files. On every pull request update the workflow will:
   * Post a "build started" comment with progress indicators.
   * Poll the build until it succeeds or fails.
   * Update the comment with completion status, log links, and preview URLs.
   * Run smoke tests against the MCP server to ensure the local proxy still boots and responds to health checks.

## Customizing the PR comment UI

The `github_actions_deploy.pr_comments.render_progress_comment` helper renders a markdown table with emoji-based status chips and
rich quick links. You can pass additional quick links with the `--quick-link` CLI flag in the workflow (e.g. `--quick-link "Staging Logs=https://..."`). The helper automatically timestamps the comment and highlights failures with callouts.

## Publishing the package

To publish the helper library to PyPI:

```bash
python -m build
python -m twine upload dist/*
```

The metadata in `pyproject.toml` is preconfigured with the package name `github-actions-deploy` and includes the necessary
classifiers for continuous integration tooling.

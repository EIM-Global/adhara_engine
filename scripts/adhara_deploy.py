"""
adhara_deploy.py — Standalone deploy script for the Adhara Engine platform.

Usage (CLI):
    python scripts/adhara_deploy.py /path/to/app \\
        --tenant acme \\
        --workspace production \\
        --site my-app \\
        --port 3000

Usage (import):
    from scripts.adhara_deploy import AdharaDeployer

    deployer = AdharaDeployer()
    result = deployer.deploy(
        app_path="/path/to/app",
        tenant_name="acme",
        workspace_name="production",
        site_name="my-app",
        container_port=3000,
    )

Environment variables:
    ADHARA_ENGINE_URL   — API base URL (default: http://localhost:8000)
    ADHARA_ENGINE_TOKEN — Bearer token for authentication (optional for local dev)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
import unicodedata
from typing import Optional

import httpx


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_REGISTRY = "localhost:5000"
POLL_INTERVAL_SECONDS = 3
TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug, matching the API's slugify logic."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    text = text.strip("-")
    return text


def _fmt_duration(duration_ms: Optional[int]) -> str:
    """Format milliseconds as a human-readable duration."""
    if duration_ms is None:
        return ""
    seconds = duration_ms / 1000.0
    return f"{seconds:.1f}s"


def _step(number: int, total: int, message: str) -> None:
    print(f"[{number}/{total}] {message}")


def _ok(message: str) -> None:
    print(f"      + {message}")


def _info(message: str) -> None:
    print(f"      -> {message}")


def _err(message: str) -> None:
    print(f"      ERROR: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DeployError(Exception):
    """Raised when any step in the deploy workflow fails."""


class APIError(Exception):
    """Raised when the Adhara Engine API returns an error response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


# ---------------------------------------------------------------------------
# AdharaDeployer
# ---------------------------------------------------------------------------


class AdharaDeployer:
    """Automates the full Adhara Engine deploy workflow.

    Steps:
        1. Preflight  — verify Docker, API, and registry are available
        2. Build      — docker build
        3. Push       — docker tag + docker push to local registry
        4. Tenant     — find or create tenant by slug
        5. Workspace  — find or create workspace by slug
        6. Site       — find or create site by slug (PATCH source_url if exists)
        7. Env vars   — PUT env vars if provided
        8. Deploy     — POST /deploy to trigger pipeline
        9. Poll       — poll pipeline until terminal status
    """

    TOTAL_STEPS = 9

    def __init__(
        self,
        api_url: Optional[str] = None,
        token: Optional[str] = None,
    ) -> None:
        self.api_url = (api_url or os.environ.get("ADHARA_ENGINE_URL", DEFAULT_API_URL)).rstrip("/")
        self.token = token or os.environ.get("ADHARA_ENGINE_TOKEN")

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=60.0,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deploy(
        self,
        app_path: str,
        tenant_name: str,
        workspace_name: str,
        site_name: str,
        container_port: int = 3000,
        env_vars: Optional[dict[str, str]] = None,
        build_args: Optional[dict[str, str]] = None,
        deploy_target: str = "local",
        owner_email: str = "admin@localhost",
        skip_build: bool = False,
    ) -> dict:
        """Execute the full deploy workflow and return the final pipeline result."""
        site_slug = slugify(site_name)
        image_tag = f"{site_slug}:latest"
        registry_image = f"{DEFAULT_REGISTRY}/{image_tag}"

        # Step 1: Preflight
        _step(1, self.TOTAL_STEPS, "Preflight checks...")
        self._preflight(app_path)

        # Step 2: Build
        if skip_build:
            _step(2, self.TOTAL_STEPS, "Skipping Docker build (--skip-build).")
        else:
            _step(2, self.TOTAL_STEPS, "Building Docker image...")
            self._build(app_path, image_tag, build_args or {})

        # Step 3: Push
        _step(3, self.TOTAL_STEPS, "Pushing to registry...")
        self._push(image_tag, registry_image)

        # Step 4: Tenant
        tenant_slug = slugify(tenant_name)
        _step(4, self.TOTAL_STEPS, f'Finding or creating tenant "{tenant_name}"...')
        tenant = self._find_or_create_tenant(tenant_name, tenant_slug, owner_email)

        # Step 5: Workspace
        workspace_slug = slugify(workspace_name)
        _step(5, self.TOTAL_STEPS, f'Finding or creating workspace "{workspace_name}"...')
        workspace = self._find_or_create_workspace(tenant["id"], workspace_name, workspace_slug)

        # Step 6: Site
        _step(6, self.TOTAL_STEPS, f'Finding or creating site "{site_name}"...')
        site = self._find_or_create_site(
            workspace_id=workspace["id"],
            site_name=site_name,
            site_slug=site_slug,
            source_url=registry_image,
            container_port=container_port,
            deploy_target=deploy_target,
        )

        # Step 7: Env vars
        _step(7, self.TOTAL_STEPS, "Setting environment variables...")
        if env_vars:
            self._set_env_vars(site["id"], env_vars)
            _ok(f"Set {len(env_vars)} env var(s)")
        else:
            _ok("No env vars provided — skipping")

        # Step 8: Trigger deploy
        _step(8, self.TOTAL_STEPS, "Triggering deployment...")
        deploy_response = self._trigger_deploy(site["id"])
        pipeline_run_id = deploy_response.get("pipeline_run_id")
        if not pipeline_run_id:
            raise DeployError(
                f"Deploy response missing pipeline_run_id: {deploy_response}"
            )
        _ok(f"Pipeline enqueued: {pipeline_run_id}")

        # Step 9: Poll pipeline
        _step(9, self.TOTAL_STEPS, "Pipeline running...")
        result = self._poll_pipeline(pipeline_run_id)

        # Print site URL on success
        if result.get("status") == "succeeded":
            site_url = self._build_site_url(site_slug, workspace_slug, tenant_slug)
            print(f"\nSite URL: {site_url}")

        return result

    # ------------------------------------------------------------------
    # Step implementations
    # ------------------------------------------------------------------

    def _preflight(self, app_path: str) -> None:
        """Verify Docker, API, and registry are accessible."""
        # Check app_path exists
        if not os.path.isdir(app_path):
            raise DeployError(f"App path does not exist or is not a directory: {app_path}")

        # Check Docker is available
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise DeployError(
                "Docker is not available or not running. "
                f"docker info returned: {result.stderr.strip()}"
            )
        _ok("Docker available")

        # Check API is reachable
        try:
            resp = self._client.get("/health")
            resp.raise_for_status()
            _ok(f"API reachable at {self.api_url}")
        except httpx.ConnectError:
            raise DeployError(f"Cannot reach Adhara Engine API at {self.api_url}")
        except httpx.HTTPStatusError as exc:
            raise DeployError(
                f"API health check failed with status {exc.response.status_code}"
            )

        # Check registry is accessible
        try:
            reg_resp = httpx.get(
                f"http://{DEFAULT_REGISTRY}/v2/",
                timeout=5.0,
            )
            # Registry returns 200 or 401 (auth required) — both mean it's up
            if reg_resp.status_code not in (200, 401):
                raise DeployError(
                    f"Registry at {DEFAULT_REGISTRY} returned unexpected status: "
                    f"{reg_resp.status_code}"
                )
            _ok(f"Registry accessible at {DEFAULT_REGISTRY}")
        except httpx.ConnectError:
            raise DeployError(
                f"Cannot reach Docker registry at {DEFAULT_REGISTRY}. "
                "Is the registry running?"
            )

    def _build(self, app_path: str, image_tag: str, build_args: dict[str, str]) -> None:
        """Build the Docker image."""
        cmd = ["docker", "build", "-t", image_tag]
        for key, value in build_args.items():
            cmd += ["--build-arg", f"{key}={value}"]
        cmd.append(app_path)

        _info(" ".join(cmd))
        result = subprocess.run(cmd, text=True)
        if result.returncode != 0:
            raise DeployError(f"docker build failed with exit code {result.returncode}")
        _ok(f"Image built: {image_tag}")

    def _push(self, image_tag: str, registry_image: str) -> None:
        """Tag and push the image to the local registry."""
        # Tag for registry
        tag_cmd = ["docker", "tag", image_tag, registry_image]
        _info(" ".join(tag_cmd))
        tag_result = subprocess.run(tag_cmd, capture_output=True, text=True)
        if tag_result.returncode != 0:
            raise DeployError(
                f"docker tag failed: {tag_result.stderr.strip()}"
            )

        # Push
        push_cmd = ["docker", "push", registry_image]
        _info(" ".join(push_cmd))
        push_result = subprocess.run(push_cmd, text=True)
        if push_result.returncode != 0:
            raise DeployError(f"docker push failed with exit code {push_result.returncode}")
        _ok(f"Pushed: {registry_image}")

    def _find_or_create_tenant(
        self, name: str, slug: str, owner_email: str
    ) -> dict:
        """Return existing tenant by slug, or create a new one."""
        tenants = self._api_get("/api/v1/tenants")
        for tenant in tenants:
            if tenant.get("slug") == slug:
                _ok(f"Found existing tenant: {slug} (id: {tenant['id']})")
                return tenant

        # Create
        tenant = self._api_post("/api/v1/tenants", {
            "name": name,
            "owner_email": owner_email,
            "plan": "free",
        })
        _ok(f"Created tenant: {slug} (id: {tenant['id']})")
        return tenant

    def _find_or_create_workspace(
        self, tenant_id: str, name: str, slug: str
    ) -> dict:
        """Return existing workspace by slug, or create a new one."""
        workspaces = self._api_get(f"/api/v1/tenants/{tenant_id}/workspaces")
        for workspace in workspaces:
            if workspace.get("slug") == slug:
                _ok(f"Found existing workspace: {slug} (id: {workspace['id']})")
                return workspace

        # Create
        workspace = self._api_post(
            f"/api/v1/tenants/{tenant_id}/workspaces",
            {"name": name},
        )
        _ok(f"Created workspace: {slug} (id: {workspace['id']})")
        return workspace

    def _find_or_create_site(
        self,
        workspace_id: str,
        site_name: str,
        site_slug: str,
        source_url: str,
        container_port: int,
        deploy_target: str,
    ) -> dict:
        """Return existing site by slug (updating source_url), or create a new one."""
        sites = self._api_get(f"/api/v1/workspaces/{workspace_id}/sites")
        for site in sites:
            if site.get("slug") == site_slug:
                # Update source_url to point at new image
                updated = self._api_patch(
                    f"/api/v1/sites/{site['id']}",
                    {"source_url": source_url},
                )
                _ok(f"Found existing site: {site_slug} (id: {site['id']}) — updated source_url")
                return updated

        # Create
        site = self._api_post(
            f"/api/v1/workspaces/{workspace_id}/sites",
            {
                "name": site_name,
                "source_type": "image",
                "source_url": source_url,
                "container_port": container_port,
                "deploy_target": deploy_target,
            },
        )
        _ok(f"Created site: {site_slug} (id: {site['id']})")
        return site

    def _set_env_vars(self, site_id: str, env_vars: dict[str, str]) -> None:
        """Bulk-set environment variables on the site."""
        payload = {
            "vars": [
                {"key": k, "value": v, "scope": "runtime"}
                for k, v in env_vars.items()
            ]
        }
        self._api_put(f"/api/v1/sites/{site_id}/env", payload)

    def _trigger_deploy(self, site_id: str) -> dict:
        """POST to trigger a deployment pipeline."""
        return self._api_post(f"/api/v1/sites/{site_id}/deploy", {})

    def _poll_pipeline(self, pipeline_run_id: str) -> dict:
        """Poll the pipeline run until it reaches a terminal status."""
        seen_stages: dict[str, str] = {}  # stage_name -> last reported status

        while True:
            pipeline = self._api_get(f"/api/v1/pipelines/{pipeline_run_id}")
            status = pipeline.get("status", "unknown")
            stages = pipeline.get("stages", [])

            # Print any stage status transitions
            for stage in sorted(stages, key=lambda s: s.get("order", 0)):
                stage_name = stage.get("name", "unknown")
                stage_status = stage.get("status", "unknown")
                duration_ms = stage.get("duration_ms")

                if seen_stages.get(stage_name) != stage_status:
                    seen_stages[stage_name] = stage_status
                    duration_str = _fmt_duration(duration_ms) if duration_ms else ""
                    suffix = f" ({duration_str})" if duration_str else ""
                    print(f"      {stage_name}: {stage_status}{suffix}")

            if status in TERMINAL_STATUSES:
                if status == "succeeded":
                    _ok("Deploy succeeded!")
                elif status == "failed":
                    _err("Deploy FAILED.")
                    # Print any stage errors
                    for stage in stages:
                        if stage.get("error"):
                            _err(f"  {stage['name']}: {stage['error']}")
                    raise DeployError(f"Pipeline {pipeline_run_id} failed.")
                elif status == "cancelled":
                    raise DeployError(f"Pipeline {pipeline_run_id} was cancelled.")
                return pipeline

            time.sleep(POLL_INTERVAL_SECONDS)

    # ------------------------------------------------------------------
    # URL construction
    # ------------------------------------------------------------------

    def _build_site_url(
        self, site_slug: str, workspace_slug: str, tenant_slug: str
    ) -> str:
        """Construct the expected site URL from slugs."""
        # Typical Adhara Engine routing pattern:
        # http://{site}.{workspace}.{tenant}.localhost
        # This may differ based on actual proxy configuration.
        base = self.api_url
        # Strip scheme + port for the domain part
        host = re.sub(r"https?://", "", base).split(":")[0]
        if host in ("localhost", "127.0.0.1"):
            return f"http://{site_slug}.{workspace_slug}.{tenant_slug}.localhost"
        return f"https://{site_slug}.{workspace_slug}.{tenant_slug}.{host}"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(resp.status_code, detail)
        if resp.status_code == 204:
            return {}
        return resp.json()

    def _api_get(self, path: str) -> list | dict:
        return self._request("GET", path)

    def _api_post(self, path: str, payload: dict) -> dict:
        return self._request("POST", path, json=payload)

    def _api_patch(self, path: str, payload: dict) -> dict:
        return self._request("PATCH", path, json=payload)

    def _api_put(self, path: str, payload: dict) -> dict:
        return self._request("PUT", path, json=payload)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_kv_list(items: list[str], flag_name: str) -> dict[str, str]:
    """Parse a list of KEY=VALUE strings into a dict."""
    result = {}
    for item in items:
        if "=" not in item:
            print(
                f"ERROR: {flag_name} value must be in KEY=VALUE format, got: {item!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        key, _, value = item.partition("=")
        result[key.strip()] = value
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy an application to the Adhara Engine platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/adhara_deploy.py ./my-app \\
      --tenant acme --workspace production --site my-app --port 3000

  python scripts/adhara_deploy.py ./my-app \\
      --tenant acme --workspace staging --site my-app \\
      --env NODE_ENV=production --env PORT=3000 \\
      --build-arg NPM_TOKEN=abc123 \\
      --skip-build

Environment variables:
  ADHARA_ENGINE_URL    API base URL (default: http://localhost:8000)
  ADHARA_ENGINE_TOKEN  Bearer token for authentication
""",
    )

    parser.add_argument(
        "app_path",
        metavar="APP_PATH",
        help="Path to the application directory containing the Dockerfile.",
    )
    parser.add_argument(
        "--tenant",
        required=True,
        metavar="NAME",
        help="Tenant name (will be slugified).",
    )
    parser.add_argument(
        "--workspace",
        required=True,
        metavar="NAME",
        help="Workspace name (will be slugified).",
    )
    parser.add_argument(
        "--site",
        required=True,
        metavar="NAME",
        help="Site name (will be slugified).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3000,
        metavar="PORT",
        help="Container port the app listens on (default: 3000).",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Runtime environment variable (repeatable).",
    )
    parser.add_argument(
        "--build-arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        dest="build_args",
        help="Docker build argument (repeatable).",
    )
    parser.add_argument(
        "--deploy-target",
        default="local",
        metavar="TARGET",
        help="Deploy target (default: local).",
    )
    parser.add_argument(
        "--owner-email",
        default="admin@localhost",
        metavar="EMAIL",
        help="Owner email for new tenant creation (default: admin@localhost).",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip the docker build step (assumes image already exists locally).",
    )
    parser.add_argument(
        "--api-url",
        default=None,
        metavar="URL",
        help=f"Adhara Engine API URL (default: {DEFAULT_API_URL} or ADHARA_ENGINE_URL env var).",
    )
    parser.add_argument(
        "--token",
        default=None,
        metavar="TOKEN",
        help="API bearer token (default: ADHARA_ENGINE_TOKEN env var).",
    )

    args = parser.parse_args()

    env_vars = _parse_kv_list(args.env, "--env") if args.env else None
    build_args = _parse_kv_list(args.build_args, "--build-arg") if args.build_args else None

    deployer = AdharaDeployer(api_url=args.api_url, token=args.token)

    try:
        deployer.deploy(
            app_path=args.app_path,
            tenant_name=args.tenant,
            workspace_name=args.workspace,
            site_name=args.site,
            container_port=args.port,
            env_vars=env_vars,
            build_args=build_args,
            deploy_target=args.deploy_target,
            owner_email=args.owner_email,
            skip_build=args.skip_build,
        )
    except DeployError as exc:
        print(f"\nDeploy failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except APIError as exc:
        print(f"\nAPI error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()

"""HTTP client wrapper for the Adhara Engine API."""

import os

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"


class EngineClient:
    """Synchronous HTTP client for the Adhara Engine API."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or os.environ.get("ADHARA_ENGINE_TOKEN", "")
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.Client(base_url=self.base_url, timeout=30.0, headers=headers)

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        resp = self._client.request(method, path, **kwargs)
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise EngineAPIError(resp.status_code, detail)
        if resp.status_code == 204:
            return {}
        return resp.json()

    # ── Tenants ──────────────────────────────────────────────────────────

    def create_tenant(self, name: str, email: str, plan: str = "free") -> dict:
        return self._request("POST", "/api/v1/tenants", json={
            "name": name, "owner_email": email, "plan": plan,
        })

    def list_tenants(self) -> list:
        return self._request("GET", "/api/v1/tenants")

    def get_tenant(self, tenant_id: str) -> dict:
        return self._request("GET", f"/api/v1/tenants/{tenant_id}")

    def update_tenant(self, tenant_id: str, **kwargs) -> dict:
        return self._request("PATCH", f"/api/v1/tenants/{tenant_id}", json=kwargs)

    def delete_tenant(self, tenant_id: str) -> dict:
        return self._request("DELETE", f"/api/v1/tenants/{tenant_id}")

    # ── Workspaces ───────────────────────────────────────────────────────

    def create_workspace(self, tenant_id: str, name: str,
                         adhara_api_url: str | None = None,
                         adhara_api_key: str | None = None) -> dict:
        payload: dict = {"name": name}
        if adhara_api_url:
            payload["adhara_api_url"] = adhara_api_url
        if adhara_api_key:
            payload["adhara_api_key"] = adhara_api_key
        return self._request("POST", f"/api/v1/tenants/{tenant_id}/workspaces", json=payload)

    def list_workspaces(self, tenant_id: str) -> list:
        return self._request("GET", f"/api/v1/tenants/{tenant_id}/workspaces")

    def get_workspace(self, workspace_id: str) -> dict:
        return self._request("GET", f"/api/v1/workspaces/{workspace_id}")

    def update_workspace(self, workspace_id: str, **kwargs) -> dict:
        return self._request("PATCH", f"/api/v1/workspaces/{workspace_id}", json=kwargs)

    def delete_workspace(self, workspace_id: str) -> dict:
        return self._request("DELETE", f"/api/v1/workspaces/{workspace_id}")

    # ── Sites ────────────────────────────────────────────────────────────

    def create_site(self, workspace_id: str, name: str, source_type: str,
                    source_url: str | None = None, container_port: int = 3000,
                    deploy_target: str = "local", **kwargs) -> dict:
        payload = {
            "name": name,
            "source_type": source_type,
            "container_port": container_port,
            "deploy_target": deploy_target,
        }
        if source_url:
            payload["source_url"] = source_url
        payload.update(kwargs)
        return self._request("POST", f"/api/v1/workspaces/{workspace_id}/sites", json=payload)

    def list_sites(self, workspace_id: str) -> list:
        return self._request("GET", f"/api/v1/workspaces/{workspace_id}/sites")

    def get_site(self, site_id: str) -> dict:
        return self._request("GET", f"/api/v1/sites/{site_id}")

    def update_site(self, site_id: str, **kwargs) -> dict:
        return self._request("PATCH", f"/api/v1/sites/{site_id}", json=kwargs)

    def delete_site(self, site_id: str) -> dict:
        return self._request("DELETE", f"/api/v1/sites/{site_id}")

    # ── Deployments ──────────────────────────────────────────────────────

    def deploy_site(self, site_id: str) -> dict:
        return self._request("POST", f"/api/v1/sites/{site_id}/deploy")

    def stop_site(self, site_id: str) -> dict:
        return self._request("POST", f"/api/v1/sites/{site_id}/stop")

    def restart_site(self, site_id: str) -> dict:
        return self._request("POST", f"/api/v1/sites/{site_id}/restart")

    def site_logs(self, site_id: str, tail: int = 100) -> dict:
        return self._request("GET", f"/api/v1/sites/{site_id}/logs", params={"tail": tail})

    def site_status(self, site_id: str) -> dict:
        return self._request("GET", f"/api/v1/sites/{site_id}/status")

    def list_deployments(self, site_id: str) -> list:
        return self._request("GET", f"/api/v1/sites/{site_id}/deployments")

    # ── Pipelines ──────────────────────────────────────────────────────────

    def list_pipelines(self, site_id: str) -> list:
        return self._request("GET", f"/api/v1/sites/{site_id}/pipelines")

    def get_pipeline(self, pipeline_run_id: str) -> dict:
        return self._request("GET", f"/api/v1/pipelines/{pipeline_run_id}")

    def cancel_pipeline(self, pipeline_run_id: str) -> dict:
        return self._request("POST", f"/api/v1/pipelines/{pipeline_run_id}/cancel")

    def retry_pipeline(self, pipeline_run_id: str) -> dict:
        return self._request("POST", f"/api/v1/pipelines/{pipeline_run_id}/retry")

    # ── Env Vars ─────────────────────────────────────────────────────────

    def list_env(self, site_id: str) -> list:
        return self._request("GET", f"/api/v1/sites/{site_id}/env")

    def set_env(self, site_id: str, key: str, value: str, scope: str = "runtime") -> dict:
        return self._request("PUT", f"/api/v1/sites/{site_id}/env", json={
            "vars": [{"key": key, "value": value, "scope": scope}],
        })

    def unset_env(self, site_id: str, key: str) -> dict:
        return self._request("DELETE", f"/api/v1/sites/{site_id}/env/{key}")

    # ── Domains ──────────────────────────────────────────────────────────

    def add_domain(self, site_id: str, domain: str) -> dict:
        return self._request("POST", f"/api/v1/sites/{site_id}/domains", json={"domain": domain})

    def list_domains(self, site_id: str) -> list:
        return self._request("GET", f"/api/v1/sites/{site_id}/domains")

    def remove_domain(self, site_id: str, domain: str) -> dict:
        return self._request("DELETE", f"/api/v1/sites/{site_id}/domains/{domain}")

    def verify_domain(self, site_id: str, domain: str) -> dict:
        return self._request("POST", f"/api/v1/sites/{site_id}/domains/{domain}/verify")

    # ── Ports ────────────────────────────────────────────────────────────

    def list_ports(self) -> list:
        return self._request("GET", "/api/v1/ports")

    def set_port(self, site_id: str, host_port: int | None = None,
                 container_port: int | None = None) -> dict:
        payload = {}
        if host_port is not None:
            payload["host_port"] = host_port
        if container_port is not None:
            payload["container_port"] = container_port
        return self._request("PATCH", f"/api/v1/sites/{site_id}/ports", json=payload)

    # ── Registry ──────────────────────────────────────────────────────────

    def list_registry(self) -> dict:
        return self._request("GET", "/api/v1/registry")

    def registry_health(self) -> dict:
        return self._request("GET", "/api/v1/registry/health")

    def get_registry_repo(self, repository: str) -> dict:
        return self._request("GET", f"/api/v1/registry/{repository}")

    def get_registry_repo_detail(self, repository: str) -> dict:
        return self._request("GET", f"/api/v1/registry/{repository}/detail")

    def delete_registry_tag(self, repository: str, tag: str) -> dict:
        return self._request("DELETE", f"/api/v1/registry/{repository}/tags/{tag}")

    def delete_registry_repo(self, repository: str) -> dict:
        return self._request("DELETE", f"/api/v1/registry/{repository}")

    # ── System ───────────────────────────────────────────────────────────

    def health(self) -> dict:
        return self._request("GET", "/health")


class EngineAPIError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")

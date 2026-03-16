"""Adhara Engine CLI — manage tenants, workspaces, sites, and deployments."""

from typing import Optional

import typer

from adhara_engine_cli.client import EngineClient, EngineAPIError
from adhara_engine_cli.output import (
    console, print_detail, print_error, print_json, print_success, print_table,
    set_json_mode,
)
from adhara_engine_cli.resolve import resolve_site, resolve_tenant, resolve_workspace

app = typer.Typer(
    name="adhara-engine",
    help="Adhara Engine — multi-tenant frontend deployment platform.",
    no_args_is_help=True,
)

# ── Global options ───────────────────────────────────────────────────────────

_client: EngineClient | None = None


def get_client() -> EngineClient:
    global _client
    if _client is None:
        _client = EngineClient()
    return _client


@app.callback()
def main(
    api_url: str = typer.Option("http://localhost:8000", "--api-url", "-u", envvar="ADHARA_ENGINE_URL",
                                help="Engine API base URL"),
    token: str = typer.Option("", "--token", "-t", envvar="ADHARA_ENGINE_TOKEN",
                              help="API token for authentication"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Adhara Engine CLI."""
    global _client
    _client = EngineClient(api_url, token=token or None)
    set_json_mode(json_output)


def _handle(func):
    """Wrap API calls with error handling."""
    try:
        return func()
    except EngineAPIError as e:
        print_error(f"{e.status_code}: {e.detail}")
    except ValueError as e:
        print_error(str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  TENANT commands
# ═══════════════════════════════════════════════════════════════════════════════

tenant_app = typer.Typer(help="Manage tenants.")
app.add_typer(tenant_app, name="tenant")


@tenant_app.command("create")
def tenant_create(
    name: str = typer.Option(..., "--name", "-n", help="Tenant name"),
    email: str = typer.Option(..., "--email", "-e", help="Owner email"),
    plan: str = typer.Option("free", "--plan", "-p", help="Plan: free, starter, pro, enterprise"),
):
    """Create a new tenant."""
    def _run():
        result = get_client().create_tenant(name, email, plan)
        print_detail(result, "Tenant created")
        return result
    _handle(_run)


@tenant_app.command("list")
def tenant_list():
    """List all tenants."""
    def _run():
        tenants = get_client().list_tenants()
        print_table(
            [("name", "Name"), ("slug", "Slug"), ("plan", "Plan"), ("owner_email", "Email"), ("id", "ID")],
            tenants,
            title="Tenants",
        )
    _handle(_run)


@tenant_app.command("update")
def tenant_update(
    slug: str = typer.Argument(..., help="Tenant slug"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    plan: Optional[str] = typer.Option(None, "--plan", "-p", help="New plan"),
    email: Optional[str] = typer.Option(None, "--email", "-e", help="New owner email"),
):
    """Update a tenant."""
    def _run():
        tenant = resolve_tenant(get_client(), slug)
        kwargs = {}
        if name:
            kwargs["name"] = name
        if plan:
            kwargs["plan"] = plan
        if email:
            kwargs["owner_email"] = email
        if not kwargs:
            print_error("Provide at least one field to update (--name, --plan, --email)")
        result = get_client().update_tenant(tenant["id"], **kwargs)
        print_detail(result, "Tenant updated")
    _handle(_run)


@tenant_app.command("delete")
def tenant_delete(
    slug: str = typer.Argument(..., help="Tenant slug"),
):
    """Delete a tenant by slug."""
    def _run():
        tenant = resolve_tenant(get_client(), slug)
        get_client().delete_tenant(tenant["id"])
        print_success(f"Tenant '{slug}' deleted")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  WORKSPACE commands
# ═══════════════════════════════════════════════════════════════════════════════

workspace_app = typer.Typer(help="Manage workspaces.")
app.add_typer(workspace_app, name="workspace")


@workspace_app.command("create")
def workspace_create(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant slug"),
    name: str = typer.Option(..., "--name", "-n", help="Workspace name"),
    adhara_api_url: Optional[str] = typer.Option(None, "--adhara-api-url", help="Adhara Web API URL"),
    adhara_api_key: Optional[str] = typer.Option(None, "--adhara-api-key", help="Adhara Web API key"),
):
    """Create a workspace under a tenant."""
    def _run():
        t = resolve_tenant(get_client(), tenant)
        result = get_client().create_workspace(t["id"], name, adhara_api_url, adhara_api_key)
        print_detail(result, "Workspace created")
    _handle(_run)


@workspace_app.command("list")
def workspace_list(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant slug"),
):
    """List workspaces for a tenant."""
    def _run():
        t = resolve_tenant(get_client(), tenant)
        workspaces = get_client().list_workspaces(t["id"])
        print_table(
            [("name", "Name"), ("slug", "Slug"), ("adhara_api_url", "Adhara API"), ("id", "ID")],
            workspaces,
            title=f"Workspaces — {tenant}",
        )
    _handle(_run)


@workspace_app.command("update")
def workspace_update(
    path: str = typer.Argument(..., help="tenant/workspace slug path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    adhara_api_url: Optional[str] = typer.Option(None, "--adhara-api-url", help="Adhara Web API URL"),
    adhara_api_key: Optional[str] = typer.Option(None, "--adhara-api-key", help="Adhara Web API key"),
):
    """Update a workspace."""
    def _run():
        ws = resolve_workspace(get_client(), path)
        kwargs = {}
        if name:
            kwargs["name"] = name
        if adhara_api_url is not None:
            kwargs["adhara_api_url"] = adhara_api_url
        if adhara_api_key is not None:
            kwargs["adhara_api_key"] = adhara_api_key
        if not kwargs:
            print_error("Provide at least one field to update")
        result = get_client().update_workspace(ws["id"], **kwargs)
        print_detail(result, "Workspace updated")
    _handle(_run)


@workspace_app.command("delete")
def workspace_delete(
    path: str = typer.Argument(..., help="tenant/workspace slug path"),
):
    """Delete a workspace (tenant/workspace)."""
    def _run():
        ws = resolve_workspace(get_client(), path)
        get_client().delete_workspace(ws["id"])
        print_success(f"Workspace '{path}' deleted")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  SITE commands
# ═══════════════════════════════════════════════════════════════════════════════

site_app = typer.Typer(help="Manage sites.")
app.add_typer(site_app, name="site")


@site_app.command("create")
def site_create(
    workspace: str = typer.Option(..., "--workspace", "-w", help="tenant/workspace slug path"),
    name: str = typer.Option(..., "--name", "-n", help="Site name"),
    source: str = typer.Option(..., "--source", "-s", help="Source type: git_repo, docker_image, docker_registry, upload"),
    image: Optional[str] = typer.Option(None, "--image", "-i", help="Docker image or git URL"),
    port: int = typer.Option(3000, "--port", "-p", help="Container port"),
    target: str = typer.Option("local", "--target", help="Deploy target: local, kubernetes, cloud_run"),
):
    """Create a new site."""
    def _run():
        ws = resolve_workspace(get_client(), workspace)
        result = get_client().create_site(
            ws["id"], name, source, source_url=image,
            container_port=port, deploy_target=target,
        )
        print_detail(result, "Site created")
    _handle(_run)


@site_app.command("list")
def site_list(
    workspace: str = typer.Option(..., "--workspace", "-w", help="tenant/workspace slug path"),
):
    """List sites in a workspace."""
    def _run():
        ws = resolve_workspace(get_client(), workspace)
        sites = get_client().list_sites(ws["id"])
        print_table(
            [("name", "Name"), ("slug", "Slug"), ("status", "Status"),
             ("source_type", "Source"), ("host_port", "Port"), ("id", "ID")],
            sites,
            title=f"Sites — {workspace}",
        )
    _handle(_run)


@site_app.command("info")
def site_info(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Show detailed site information."""
    def _run():
        site = resolve_site(get_client(), path)
        print_detail(site, f"Site — {path}")
    _handle(_run)


@site_app.command("update")
def site_update(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    source_url: Optional[str] = typer.Option(None, "--source-url", help="New source URL"),
    branch: Optional[str] = typer.Option(None, "--branch", help="Git branch"),
    auto_deploy: Optional[bool] = typer.Option(None, "--auto-deploy/--no-auto-deploy", help="Enable/disable auto-deploy"),
    health_path: Optional[str] = typer.Option(None, "--health-path", help="Health check path"),
):
    """Update a site's configuration."""
    def _run():
        site = resolve_site(get_client(), path)
        kwargs = {}
        if name:
            kwargs["name"] = name
        if source_url:
            kwargs["source_url"] = source_url
        if branch:
            kwargs["git_branch"] = branch
        if auto_deploy is not None:
            kwargs["auto_deploy"] = auto_deploy
        if health_path:
            kwargs["health_check_path"] = health_path
        if not kwargs:
            print_error("Provide at least one field to update")
        result = get_client().update_site(site["id"], **kwargs)
        print_detail(result, f"Site updated — {path}")
    _handle(_run)


@site_app.command("delete")
def site_delete(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Delete a site."""
    def _run():
        site = resolve_site(get_client(), path)
        get_client().delete_site(site["id"])
        print_success(f"Site '{path}' deleted")
    _handle(_run)


@site_app.command("deploy")
def site_deploy(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Deploy a site."""
    def _run():
        site = resolve_site(get_client(), path)
        with console.status(f"Deploying {path}...", spinner="dots"):
            result = get_client().deploy_site(site["id"])
        print_detail(result, f"Deployment — {path}")
        # Show site URL after successful deploy
        if result.get("status") == "live":
            parts = path.split("/")
            if len(parts) == 3:
                tenant_slug, ws_slug, site_slug = parts
                url = f"http://{site_slug}.{ws_slug}.{tenant_slug}.localhost"
                console.print(f"  [bold green]Site URL:[/bold green] {url}")
                console.print()
    _handle(_run)


@site_app.command("stop")
def site_stop(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Stop a running site."""
    def _run():
        site = resolve_site(get_client(), path)
        get_client().stop_site(site["id"])
        print_success(f"Site '{path}' stopped")
    _handle(_run)


@site_app.command("restart")
def site_restart(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Restart a site."""
    def _run():
        site = resolve_site(get_client(), path)
        get_client().restart_site(site["id"])
        print_success(f"Site '{path}' restarted")
    _handle(_run)


@site_app.command("logs")
def site_logs(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of log lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream logs in real-time"),
):
    """View site container logs."""
    def _run():
        site = resolve_site(get_client(), path)
        if follow:
            # For --follow, use streaming (future: SSE endpoint)
            # For now, just poll with tail
            console.print(f"[dim]Streaming logs for {path} (Ctrl+C to stop)...[/dim]")
            result = get_client().site_logs(site["id"], tail=tail)
        else:
            result = get_client().site_logs(site["id"], tail=tail)

        lines = result.get("lines") or result.get("logs") or []
        if isinstance(lines, list):
            for line in lines:
                console.print(line)
        else:
            console.print(str(lines))
    _handle(_run)


@site_app.command("status")
def site_status_cmd(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """Show container status for a site."""
    def _run():
        site = resolve_site(get_client(), path)
        result = get_client().site_status(site["id"])
        print_detail(result, f"Container Status — {path}")
    _handle(_run)


@site_app.command("set-port")
def site_set_port(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    host_port: Optional[int] = typer.Option(None, "--host", help="Host port"),
    container_port: Optional[int] = typer.Option(None, "--container", help="Container port"),
):
    """Change host or container port for a site."""
    def _run():
        if host_port is None and container_port is None:
            print_error("Specify --host and/or --container port")
        site = resolve_site(get_client(), path)
        result = get_client().set_port(site["id"], host_port, container_port)
        print_detail(result, f"Port updated — {path}")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  ENV commands
# ═══════════════════════════════════════════════════════════════════════════════

env_app = typer.Typer(help="Manage site environment variables.")
app.add_typer(env_app, name="env")


@env_app.command("list")
def env_list(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """List environment variables for a site."""
    def _run():
        site = resolve_site(get_client(), path)
        data = get_client().list_env(site["id"])
        rows = []
        for key, value in (data.get("runtime_env") or {}).items():
            rows.append({"key": key, "value": value, "scope": "runtime"})
        for key, value in (data.get("build_env") or {}).items():
            rows.append({"key": key, "value": value, "scope": "build"})
        print_table(
            [("key", "Key"), ("value", "Value"), ("scope", "Scope")],
            rows,
            title=f"Env Vars — {path}",
        )
    _handle(_run)


@env_app.command("set")
def env_set(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    key_value: str = typer.Argument(..., help="KEY=VALUE pair"),
    build: bool = typer.Option(False, "--build", "-b", help="Set as build-time variable (requires rebuild)"),
):
    """Set an environment variable. Auto-detects NEXT_PUBLIC_* as build scope."""
    def _run():
        if "=" not in key_value:
            print_error("Expected KEY=VALUE format")
        key, value = key_value.split("=", 1)
        scope = "build" if build else "runtime"
        site = resolve_site(get_client(), path)
        result = get_client().set_env(site["id"], key, value, scope)
        print_detail(result, f"Env var set — {path}")
    _handle(_run)


@env_app.command("unset")
def env_unset(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    key: str = typer.Argument(..., help="Environment variable key"),
):
    """Remove an environment variable."""
    def _run():
        site = resolve_site(get_client(), path)
        get_client().unset_env(site["id"], key)
        print_success(f"Env var '{key}' removed from {path}")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  DOMAIN commands
# ═══════════════════════════════════════════════════════════════════════════════

domain_app = typer.Typer(help="Manage custom domains.")
app.add_typer(domain_app, name="domain")


@domain_app.command("add")
def domain_add(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    domain: str = typer.Argument(..., help="Custom domain (e.g. app.example.com)"),
):
    """Add a custom domain to a site."""
    def _run():
        site = resolve_site(get_client(), path)
        result = get_client().add_domain(site["id"], domain)
        print_detail(result, "Domain added")
        if not result.get("verified"):
            console.print("\n[yellow]Configure these DNS records:[/yellow]")
            for rec in result.get("dns_records", []):
                console.print(f"  {rec['type']}  {rec['name']}  →  {rec['value']}")
    _handle(_run)


@domain_app.command("list")
def domain_list(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """List custom domains for a site."""
    def _run():
        site = resolve_site(get_client(), path)
        domains = get_client().list_domains(site["id"])
        print_table(
            [("domain", "Domain"), ("verified", "Verified")],
            domains,
            title=f"Domains — {path}",
        )
    _handle(_run)


@domain_app.command("remove")
def domain_remove(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    domain: str = typer.Argument(..., help="Domain to remove"),
):
    """Remove a custom domain."""
    def _run():
        site = resolve_site(get_client(), path)
        get_client().remove_domain(site["id"], domain)
        print_success(f"Domain '{domain}' removed from {path}")
    _handle(_run)


@domain_app.command("verify")
def domain_verify(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
    domain: str = typer.Argument(..., help="Domain to verify"),
):
    """Check DNS propagation for a domain."""
    def _run():
        site = resolve_site(get_client(), path)
        result = get_client().verify_domain(site["id"], domain)
        if result.get("verified"):
            print_success(f"Domain '{domain}' is verified and pointing to engine")
        else:
            console.print(f"[yellow]Domain '{domain}' is NOT yet verified.[/yellow]")
            console.print("Ensure DNS records are configured and propagated.")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  DEPLOY commands
# ═══════════════════════════════════════════════════════════════════════════════

deploy_app = typer.Typer(help="Deployment history and rollback.")
app.add_typer(deploy_app, name="deploy")


@deploy_app.command("list")
def deploy_list(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """List deployment history for a site."""
    def _run():
        site = resolve_site(get_client(), path)
        deployments = get_client().list_deployments(site["id"])
        print_table(
            [("version", "Ver"), ("status", "Status"), ("image_tag", "Image"),
             ("host_port", "Port"), ("created_at", "Created"), ("deployed_at", "Deployed")],
            deployments,
            title=f"Deployments — {path}",
        )
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  PIPELINE commands
# ═══════════════════════════════════════════════════════════════════════════════

pipeline_app = typer.Typer(help="Track and manage deployment pipelines.")
app.add_typer(pipeline_app, name="pipeline")


@pipeline_app.command("list")
def pipeline_list(
    path: str = typer.Argument(..., help="tenant/workspace/site slug path"),
):
    """List pipeline runs for a site."""
    def _run():
        site = resolve_site(get_client(), path)
        pipelines = get_client().list_pipelines(site["id"])
        print_table(
            [("id", "Pipeline ID"), ("status", "Status"), ("created_at", "Created")],
            pipelines[:20],
            title=f"Pipelines — {path}",
        )
    _handle(_run)


@pipeline_app.command("info")
def pipeline_info(
    pipeline_id: str = typer.Argument(..., help="Pipeline run ID"),
):
    """Show pipeline details and stages."""
    def _run():
        result = get_client().get_pipeline(pipeline_id)
        print_detail(result, f"Pipeline — {pipeline_id}")
    _handle(_run)


@pipeline_app.command("cancel")
def pipeline_cancel(
    pipeline_id: str = typer.Argument(..., help="Pipeline run ID"),
):
    """Cancel a running pipeline."""
    def _run():
        get_client().cancel_pipeline(pipeline_id)
        print_success(f"Pipeline {pipeline_id} cancelled")
    _handle(_run)


@pipeline_app.command("retry")
def pipeline_retry(
    pipeline_id: str = typer.Argument(..., help="Pipeline run ID"),
):
    """Retry a failed pipeline."""
    def _run():
        result = get_client().retry_pipeline(pipeline_id)
        print_detail(result, "Pipeline retried")
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  PORTS command
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("ports")
def ports():
    """Show the port routing table across all sites."""
    def _run():
        port_table = get_client().list_ports()
        print_table(
            [("site_slug", "Site"), ("tenant_slug", "Tenant"), ("workspace_slug", "Workspace"),
             ("host_port", "Host Port"), ("container_port", "Container Port"), ("status", "Status")],
            port_table,
            title="Port Routing Table",
        )
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  STATUS command
# ═══════════════════════════════════════════════════════════════════════════════

@app.command("status")
def status():
    """System health overview."""
    def _run():
        health = get_client().health()
        console.print(f"\n[bold]Adhara Engine[/bold] — {health.get('version', 'unknown')}")
        console.print(f"  Status: [green]{health.get('status', 'unknown')}[/green]")
        console.print(f"  API: {get_client().base_url}")
        console.print()

        # Show summary counts
        try:
            tenants = get_client().list_tenants()
            console.print(f"  Tenants: {len(tenants)}")
            total_sites = 0
            running = 0
            for t in tenants:
                workspaces = get_client().list_workspaces(t["id"])
                for w in workspaces:
                    sites = get_client().list_sites(w["id"])
                    total_sites += len(sites)
                    running += sum(1 for s in sites if s.get("status") == "running")
            console.print(f"  Sites: {total_sites} ({running} running)")
        except Exception:
            pass
        console.print()
    _handle(_run)


# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRY commands
# ═══════════════════════════════════════════════════════════════════════════════

registry_app = typer.Typer(help="Manage the Docker image registry.")
app.add_typer(registry_app, name="registry")


@registry_app.command("list")
def registry_list():
    """List all repositories in the registry."""
    def _run():
        data = get_client().list_registry()
        repos = data.get("repositories", [])
        if data.get("error"):
            print_error(data["error"])
        rows = []
        for r in repos:
            rows.append({
                "repository": r["repository"],
                "tags": len(r.get("tags", [])),
                "site": r.get("site_name") or r.get("site_slug") or "—",
                "tenant": r.get("tenant_slug") or "—",
                "workspace": r.get("workspace_slug") or "—",
            })
        print_table(
            [("repository", "Repository"), ("tags", "Tags"), ("site", "Site"),
             ("tenant", "Tenant"), ("workspace", "Workspace")],
            rows,
            title="Docker Registry",
        )
    _handle(_run)


@registry_app.command("info")
def registry_info(
    repository: str = typer.Argument(..., help="Repository name (e.g. ae-my-site)"),
):
    """Show detailed tag information for a repository."""
    def _run():
        data = get_client().get_registry_repo_detail(repository)
        tag_details = data.get("tag_details", [])

        # Print repo header
        console.print(f"\n[bold]Repository — {repository}[/bold]")
        if data.get("site_name"):
            console.print(f"  [cyan]Linked site:[/cyan] {data['site_name']}")
        if data.get("tenant_slug") and data.get("workspace_slug"):
            console.print(f"  [cyan]Path:[/cyan] {data['tenant_slug']}/{data['workspace_slug']}")
        console.print()

        if not tag_details:
            console.print("  [dim]No tags found[/dim]\n")
            return

        rows = []
        for td in tag_details:
            size = td.get("size", 0)
            if size >= 1_048_576:
                size_str = f"{size / 1_048_576:.1f} MB"
            elif size >= 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size} B"

            digest = td.get("digest", "")
            short = digest.split(":")[-1][:12] if ":" in digest else digest[:12]

            rows.append({
                "tag": td["tag"],
                "digest": f"sha256:{short}" if short else "—",
                "size": size_str,
                "layers": str(td.get("layers", 0)),
                "arch": td.get("architecture") or "—",
                "created": (td.get("created") or "—")[:19],
            })

        print_table(
            [("tag", "Tag"), ("digest", "Digest"), ("size", "Size"),
             ("layers", "Layers"), ("arch", "Platform"), ("created", "Created")],
            rows,
            title=f"Tags — {repository}",
        )
    _handle(_run)


@registry_app.command("tags")
def registry_tags(
    repository: str = typer.Argument(..., help="Repository name (e.g. ae-my-site)"),
):
    """List tags for a repository (lightweight)."""
    def _run():
        data = get_client().get_registry_repo(repository)
        tags = data.get("tags", [])
        if not tags:
            console.print(f"[dim]No tags in {repository}[/dim]")
            return
        rows = [{"tag": t} for t in tags]
        print_table(
            [("tag", "Tag")],
            rows,
            title=f"Tags — {repository}",
        )
    _handle(_run)


@registry_app.command("delete-tag")
def registry_delete_tag(
    repository: str = typer.Argument(..., help="Repository name"),
    tag: str = typer.Argument(..., help="Tag to delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete a specific tag from a repository."""
    def _run():
        if not yes:
            confirm = typer.confirm(f"Delete tag '{tag}' from {repository}?")
            if not confirm:
                raise typer.Abort()
        result = get_client().delete_registry_tag(repository, tag)
        print_success(f"Tag '{tag}' deleted from {repository}")
    _handle(_run)


@registry_app.command("delete")
def registry_delete(
    repository: str = typer.Argument(..., help="Repository name"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """Delete all tags from a repository."""
    def _run():
        # Show tag count first
        data = get_client().get_registry_repo(repository)
        tag_count = len(data.get("tags", []))

        if not yes:
            confirm = typer.confirm(
                f"Delete repository '{repository}' ({tag_count} tags)? This cannot be undone"
            )
            if not confirm:
                raise typer.Abort()

        with console.status(f"Deleting {tag_count} tags...", spinner="dots"):
            result = get_client().delete_registry_repo(repository)

        deleted = result.get("deleted_tags", 0)
        errors = result.get("errors") or []
        print_success(f"Repository '{repository}' deleted ({deleted} tags removed)")
        if errors:
            for err in errors:
                console.print(f"  [yellow]Warning:[/yellow] {err}")
    _handle(_run)


@registry_app.command("health")
def registry_health_cmd():
    """Check registry health and show stats."""
    def _run():
        h = get_client().registry_health()
        if h.get("reachable"):
            console.print(f"\n[bold green]Registry is healthy[/bold green]")
        else:
            console.print(f"\n[bold red]Registry is unreachable[/bold red]")
            if h.get("error"):
                console.print(f"  Error: {h['error']}")
            console.print()
            return

        console.print(f"  Repositories: {h.get('repository_count', 0)}")
        console.print(f"  Total tags:   {h.get('total_tags', 0)}")
        console.print()
    _handle(_run)


@registry_app.command("push")
def registry_push_info():
    """Show instructions for pushing images to the registry."""
    api_url = get_client().base_url
    # Derive registry host from API URL
    from urllib.parse import urlparse
    parsed = urlparse(api_url)
    host = parsed.hostname or "localhost"
    registry_host = f"{host}:5000"

    console.print(f"\n[bold]Push images to the Adhara Engine registry[/bold]\n")
    console.print(f"  Registry: [cyan]{registry_host}[/cyan]\n")
    console.print("[bold]Steps:[/bold]")
    console.print(f"  1. Build your image:")
    console.print(f"     [green]$ docker build -t {registry_host}/my-app:latest .[/green]\n")
    console.print(f"  2. Or tag an existing image:")
    console.print(f"     [green]$ docker tag my-app:latest {registry_host}/my-app:latest[/green]\n")
    console.print(f"  3. Push to registry:")
    console.print(f"     [green]$ docker push {registry_host}/my-app:latest[/green]\n")
    console.print(f"  4. Deploy as a site:")
    console.print(f"     [green]$ adhara-engine site create \\")
    console.print(f"         --workspace tenant/workspace \\")
    console.print(f"         --name my-app \\")
    console.print(f"         --source docker_image \\")
    console.print(f"         --image {registry_host}/my-app:latest[/green]\n")
    console.print("[dim]For remote access, use SSH tunnel: ssh -L 5000:localhost:5000 user@server[/dim]\n")


if __name__ == "__main__":
    app()

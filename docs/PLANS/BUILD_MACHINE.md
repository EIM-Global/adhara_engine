Updated Architecture — All Decisions Applied                                                                                                                                  
                                                                                                                                                                                
  Here's the complete picture with your decisions integrated:                                                                                                                   
                                                                                                                                                                                
  ---
  The Three Subsystems

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    ADHARA ENGINE - BUILD PIPELINE                    │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │   ┌───────────────────┐                                            │
  │   │  GIT PROVIDER     │  GitHub webhook ──┐                        │
  │   │  LAYER            │  GitLab webhook ──┼──▶ Normalized          │
  │   │                   │  Polling fallback ─┘    PushEvent          │
  │   └───────────────────┘                            │               │
  │                                                    ▼               │
  │   ┌───────────────────────────────────────────────────────────┐    │
  │   │  PIPELINE ENGINE (ARQ / Redis-backed)                     │    │
  │   │                                                           │    │
  │   │  PipelineRun                                              │    │
  │   │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐         │    │
  │   │  │ CLONE  │─▶│  SCAN  │─▶│ BUILD  │─▶│ DEPLOY │         │    │
  │   │  │        │  │(opt)   │  │+ PUSH  │  │        │         │    │
  │   │  └────────┘  └────────┘  └────────┘  └────────┘         │    │
  │   │  Each stage = PipelineStage row with status + logs        │    │
  │   └───────────────────────────────────────────────────────────┘    │
  │                         │                                          │
  │                    BUILD stage calls:                               │
  │                         ▼                                          │
  │   ┌───────────────────────────────────────────────────────────┐    │
  │   │  BUILD DRIVER LAYER                                       │    │
  │   │                                                           │    │
  │   │  site.build_driver ──▶ ┌─ LocalDockerBuilder              │    │
  │   │         OR             ├─ LocalBuildKitBuilder             │    │
  │   │  global default  ──▶   ├─ RemoteBuildKitBuilder            │    │
  │   │                        ├─ GCPCloudBuildDriver              │    │
  │   │                        └─ AWSCodeBuildDriver               │    │
  │   └───────────────────────────────────────────────────────────┘    │
  │                                                                     │
  │                    DEPLOY stage calls:                               │
  │                         ▼                                          │
  │   ┌───────────────────────────────────────────────────────────┐    │
  │   │  DEPLOY TARGET LAYER (existing)                           │    │
  │   │  LocalDeployTarget ──▶ docker run + Traefik labels        │    │
  │   └───────────────────────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────────────────────────┘

  ---
  New Data Models

  # ── Pipeline Models (NEW) ─────────────────────────────────────

  class PipelineRun(Base):
      __tablename__ = "pipeline_runs"

      id          = Column(UUID, primary_key=True, default=uuid4)
      site_id     = Column(UUID, ForeignKey("sites.id"), nullable=False)
      tenant_id   = Column(UUID, ForeignKey("tenants.id"), nullable=False)

      # What triggered this pipeline
      trigger         = Column(String)    # "webhook", "manual", "polling", "rollback"
      git_provider    = Column(String)    # "github", "gitlab"
      git_ref         = Column(String)    # "refs/heads/main"
      commit_sha      = Column(String)
      commit_message  = Column(String, nullable=True)
      commit_author   = Column(String, nullable=True)

      # Pipeline state
      status      = Column(String, default="pending")
      # pending → running → succeeded / failed / cancelled

      # What build driver was used
      build_driver = Column(String)      # "local_docker", "remote_buildkit", "gcp_cloud_build"

      # Result
      image_ref   = Column(String, nullable=True)   # registry.example.com/app@sha256:...
      deployment_id = Column(UUID, ForeignKey("deployments.id"), nullable=True)

      # Timing
      started_at  = Column(DateTime, nullable=True)
      finished_at = Column(DateTime, nullable=True)

      # Relationships
      stages      = relationship("PipelineStage", back_populates="pipeline_run", order_by="PipelineStage.order")
      site        = relationship("Site", back_populates="pipeline_runs")


  class PipelineStage(Base):
      __tablename__ = "pipeline_stages"

      id              = Column(UUID, primary_key=True, default=uuid4)
      pipeline_run_id = Column(UUID, ForeignKey("pipeline_runs.id"), nullable=False)

      name    = Column(String)           # "clone", "scan", "build", "push", "deploy"
      order   = Column(Integer)          # 0, 1, 2, 3, 4
      status  = Column(String, default="pending")
      # pending → running → passed / failed / skipped

      started_at  = Column(DateTime, nullable=True)
      finished_at = Column(DateTime, nullable=True)
      duration_ms = Column(Integer, nullable=True)
      logs        = Column(Text, nullable=True)
      error       = Column(Text, nullable=True)

      # Stage-specific metadata (e.g., scan results, image tag)
      metadata    = Column(JSONB, default=dict)

      pipeline_run = relationship("PipelineRun", back_populates="stages")

  # ── Git Provider Config (NEW — on Site model) ────────────────

  class Site(Base):
      # ... existing fields ...

      # Git-follow configuration
      git_provider        = Column(String, nullable=True)   # "github" | "gitlab"
      git_provider_url    = Column(String, nullable=True)   # "https://gitlab.company.com" (self-hosted)
      git_branch          = Column(String, default="main")
      auto_deploy         = Column(Boolean, default=False)
      webhook_secret      = Column(String, nullable=True)   # per-site webhook secret
      last_deployed_sha   = Column(String, nullable=True)   # dedup key

      # Clone credentials
      git_token_username  = Column(String, nullable=True)   # deploy token username
      git_token           = Column(String, nullable=True)   # deploy token (encrypted at rest)

      # Build driver override (null = use global default)
      build_driver        = Column(String, nullable=True)   # "local_docker", "remote_buildkit", etc.

      # Scan configuration
      scan_enabled        = Column(Boolean, default=False)
      scan_fail_on        = Column(String, default="critical")  # "critical", "high", "medium"

      # Relationships
      pipeline_runs = relationship("PipelineRun", back_populates="site", order_by="PipelineRun.created_at.desc()")

  # ── Global Platform Settings (NEW) ───────────────────────────

  class PlatformSettings(Base):
      __tablename__ = "platform_settings"

      id    = Column(UUID, primary_key=True, default=uuid4)
      key   = Column(String, unique=True, nullable=False)
      value = Column(JSONB, nullable=False)

      # Key examples:
      # "default_build_driver" → "local_docker"
      # "default_scan_enabled" → true
      # "default_scan_tool" → "semgrep"
      # "remote_buildkit_host" → "tcp://build-server:1234"
      # "gcp_project_id" → "my-project"

  ---
  Build Driver Interface (Per-Site with Global Default)

  class BuildDriverRegistry:
      """Resolves which build driver to use for a given site."""

      drivers: dict[str, type[BuildDriver]] = {
          "local_docker": LocalDockerBuilder,
          "local_buildkit": LocalBuildKitBuilder,
          "remote_buildkit": RemoteBuildKitBuilder,
          "gcp_cloud_build": GCPCloudBuildDriver,
          "aws_codebuild": AWSCodeBuildDriver,
      }

      @classmethod
      def get_driver(cls, site: Site, platform_settings: dict) -> BuildDriver:
          """Per-site override → global default → local_docker fallback."""
          driver_name = (
              site.build_driver                                    # per-site override
              or platform_settings.get("default_build_driver")     # global default
              or "local_docker"                                    # ultimate fallback
          )
          driver_cls = cls.drivers[driver_name]
          return driver_cls(config=platform_settings)

  ---
  Scanner Interface (Semgrep First, Fortify Later)

  class ScanDriver(ABC):
      """Pluggable code scanner."""

      @abstractmethod
      async def scan(self, source_dir: str, config: dict) -> ScanResult: ...


  @dataclass
  class ScanResult:
      passed: bool                   # True if no findings above threshold
      findings: list[ScanFinding]
      summary: dict                  # {"critical": 0, "high": 2, "medium": 5, ...}
      raw_output: str


  @dataclass
  class ScanFinding:
      severity: str                  # "critical", "high", "medium", "low", "info"
      rule_id: str                   # "python.lang.security.audit.dangerous-exec"
      message: str
      file: str
      line: int


  class SemgrepScanner(ScanDriver):
      """Static analysis via Semgrep (open source, language-aware)."""

      async def scan(self, source_dir: str, config: dict) -> ScanResult:
          # Semgrep runs via CLI, outputs JSON
          # Uses rulesets: "p/default" covers OWASP Top 10
          cmd = [
              "semgrep", "scan",
              "--config", "p/default",       # community ruleset
              "--json",                       # structured output
              "--quiet",                      # suppress progress
              source_dir,
          ]
          proc = await asyncio.create_subprocess_exec(
              *cmd, stdout=PIPE, stderr=PIPE
          )
          stdout, stderr = await proc.communicate()
          results = json.loads(stdout)

          findings = [
              ScanFinding(
                  severity=r["extra"]["severity"],
                  rule_id=r["check_id"],
                  message=r["extra"]["message"],
                  file=r["path"],
                  line=r["start"]["line"],
              )
              for r in results.get("results", [])
          ]

          summary = Counter(f.severity for f in findings)
          fail_threshold = config.get("fail_on", "critical")
          severity_order = ["info", "low", "medium", "high", "critical"]
          fail_idx = severity_order.index(fail_threshold)

          passed = not any(
              f.severity in severity_order[fail_idx:]
              for f in findings
          )

          return ScanResult(
              passed=passed,
              findings=findings,
              summary=dict(summary),
              raw_output=stdout.decode(),
          )


  class FortifyScanner(ScanDriver):
      """Future: Fortify Static Code Analyzer integration."""

      async def scan(self, source_dir: str, config: dict) -> ScanResult:
          # Fortify uses sourceanalyzer CLI or SSC REST API
          # sourceanalyzer -b <build_id> <source_dir>
          # sourceanalyzer -b <build_id> -scan -f results.fpr
          raise NotImplementedError("Fortify integration coming in Phase 4")

  Why Semgrep first:
  - Open source, free for local use
  - Supports 30+ languages out of the box
  - OWASP Top 10 ruleset included (p/default)
  - JSON output makes parsing trivial
  - Runs in seconds for most codebases
  - No server/license needed (unlike Fortify's SSC)

  ---
  ARQ Worker Setup

  # api/app/workers/pipeline_worker.py

  from arq import create_pool
  from arq.connections import RedisSettings

  async def run_pipeline(ctx: dict, pipeline_run_id: str):
      """ARQ task: execute a full pipeline run."""
      db = ctx["db"]
      pipeline = await get_pipeline_run(db, pipeline_run_id)
      site = pipeline.site

      for stage in pipeline.stages:
          await update_stage(db, stage.id, status="running")

          try:
              if stage.name == "clone":
                  result = await clone_source(site, pipeline)
              elif stage.name == "scan":
                  if not site.scan_enabled:
                      await update_stage(db, stage.id, status="skipped")
                      continue
                  result = await run_scan(site, pipeline)
                  if not result.passed:
                      await update_stage(db, stage.id, status="failed",
                                         metadata={"findings": result.summary})
                      await fail_pipeline(db, pipeline.id, f"Scan failed: {result.summary}")
                      return
              elif stage.name == "build":
                  driver = BuildDriverRegistry.get_driver(site, get_platform_settings(db))
                  result = await driver.build(build_request_from(site, pipeline))
              elif stage.name == "push":
                  # Push to local registry (localhost:5000) or configured registry
                  result = await push_to_registry(site, pipeline)
              elif stage.name == "deploy":
                  # Use existing DeployTarget
                  result = await deploy_container(site, pipeline)

              await update_stage(db, stage.id, status="passed",
                                 duration_ms=result.duration_ms, logs=result.logs)

          except Exception as e:
              await update_stage(db, stage.id, status="failed", error=str(e))
              await fail_pipeline(db, pipeline.id, str(e))
              return

      await complete_pipeline(db, pipeline.id)


  class WorkerSettings:
      """ARQ worker configuration."""
      redis_settings = RedisSettings(host="redis", port=6379)
      functions = [run_pipeline]
      max_jobs = 4                    # concurrent pipelines
      job_timeout = 600               # 10 min max per pipeline

      async def on_startup(ctx):
          ctx["db"] = SessionLocal()

      async def on_shutdown(ctx):
          ctx["db"].close()

  # docker-compose.yml — new service
    worker:
      build: ./api
      command: arq app.workers.pipeline_worker.WorkerSettings
      volumes:
        - ${DOCKER_HOST_SOCKET:-/var/run/docker.sock}:/var/run/docker.sock
      environment:
        - DATABASE_URL=postgresql://engine:${POSTGRES_PASSWORD:-engine}@db:5432/adhara_engine
        - REDIS_URL=redis://redis:6379
      depends_on:
        db: { condition: service_healthy }
        redis: { condition: service_healthy }
      networks:
        - adhara-engine-net
      restart: unless-stopped

  ---
  Git Provider Layer (GitHub + GitLab)

  # api/app/services/git_providers.py

  class GitProviderWebhook(ABC):
      @abstractmethod
      def verify(self, headers: dict, raw_body: bytes) -> None: ...

      @abstractmethod
      def parse_push(self, payload: dict) -> PushEvent: ...


  class GitHubWebhook(GitProviderWebhook):
      def verify(self, headers: dict, raw_body: bytes):
          sig = headers.get("x-hub-signature-256", "")
          expected = "sha256=" + hmac.new(
              self.secret.encode(), raw_body, hashlib.sha256
          ).hexdigest()
          if not hmac.compare_digest(sig, expected):
              raise ValueError("Invalid GitHub signature")

      def parse_push(self, payload: dict) -> PushEvent:
          # ... normalize to PushEvent (see research output above)


  class GitLabWebhook(GitProviderWebhook):
      def verify(self, headers: dict, raw_body: bytes):
          token = headers.get("x-gitlab-token", "")
          if not hmac.compare_digest(token, self.secret):
              raise ValueError("Invalid GitLab token")

      def parse_push(self, payload: dict) -> PushEvent:
          # Key difference: use checkout_sha, project.git_http_url,
          # project.path_with_namespace, project.id (numeric)

  # Unified endpoint: POST /api/v1/webhooks/{provider}

  Key GitLab differences from GitHub:
  - Signature is plain token comparison (not HMAC) — X-Gitlab-Token header
  - Use checkout_sha (not after) for the commit to build
  - Clone URL is project.git_http_url (not repository.clone_url)
  - Self-hosted GitLab admin must enable "Allow requests to local network" for internal webhook URLs
  - Deploy Tokens are the recommended clone credential (project-scoped, not user-tied)

  ---
  How Pipeline Relates to Existing Deployment Model

  Before (today):
    POST /deploy → synchronous build → Deployment(status=live)

  After:
    POST /deploy ──────────────────────────────────────┐
    POST /webhooks/{provider} ──▶ PushEvent ───────────┤
    Polling fallback ──▶ PushEvent ────────────────────┤
                                                       ▼
                                                PipelineRun (ARQ job)
                                                       │
                                      ┌────┬───────┬───┴───┬────────┐
                                      ▼    ▼       ▼       ▼        ▼
                                    clone  scan  build   push    deploy
                                                                    │
                                                                    ▼
                                                              Deployment(status=live)
                                                              (created by deploy stage)

  The existing Deployment model stays — it represents the result (which image is running, when it deployed). PipelineRun represents the process (how it got there, with full
  stage-by-stage visibility).

  ---
  Implementation Phases (Updated)

  ┌───────┬─────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────────┬────────────────────────────────────────────┐
  │ Phase │                              What                               │                    New Files                    │                  Touches                   │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 1a    │ PipelineRun + PipelineStage models, Alembic migration           │ models/pipeline.py, migration                   │ -                                          │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 1b    │ BuildDriver ABC + LocalDockerBuilder (extract from              │ services/build_drivers/,                        │ local_deploy.py                            │
  │       │ local_deploy.py)                                                │ services/build_driver.py                        │                                            │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 1c    │ ARQ worker + run_pipeline task                                  │ workers/pipeline_worker.py, docker-compose      │ requirements.txt                           │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 1d    │ Wire POST /deploy to enqueue pipeline instead of sync deploy    │ -                                               │ routers/deployments.py,                    │
  │       │                                                                 │                                                 │ container_manager.py                       │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 2a    │ GitProviderWebhook ABC + GitHub + GitLab implementations        │ services/git_providers.py                       │ -                                          │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 2b    │ Webhook receiver endpoint                                       │ routers/webhooks.py                             │ -                                          │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 2c    │ Polling fallback (background ARQ cron)                          │ workers/git_poller.py                           │ -                                          │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 2d    │ Git provider config on Site model + migration                   │ -                                               │ models/site.py                             │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 3a    │ ScanDriver ABC + SemgrepScanner                                 │ services/scanners/                              │ -                                          │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 3b    │ Wire scan stage into pipeline + Semgrep Docker image            │ -                                               │ pipeline_worker.py, Dockerfile             │
  ├───────┼─────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼────────────────────────────────────────────┤
  │ 4     │ RemoteBuildKitBuilder, cloud drivers                            │ services/build_drivers/remote.py, etc.          │ -                                          │
  └───────┴─────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────────┴────────────────────────────────────────────┘

  ---
  New API Endpoints

  ┌───────────────────────────────┬─────────┬─────────────────────────────────────────────────┐
  │           Endpoint            │ Method  │                     Purpose                     │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/webhooks/github       │ POST    │ GitHub push webhook receiver                    │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/webhooks/gitlab       │ POST    │ GitLab push webhook receiver                    │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/sites/{id}/pipelines  │ GET     │ List pipeline runs for a site                   │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/pipelines/{id}        │ GET     │ Get pipeline run with all stages                │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/pipelines/{id}/cancel │ POST    │ Cancel a running pipeline                       │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/pipelines/{id}/retry  │ POST    │ Retry a failed pipeline                         │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/sites/{id}/git-config │ PUT     │ Configure git provider, branch, auto-deploy     │
  ├───────────────────────────────┼─────────┼─────────────────────────────────────────────────┤
  │ /api/v1/platform/settings     │ GET/PUT │ Global platform settings (default driver, etc.) │
  └───────────────────────────────┴─────────┴─────────────────────────────────────────────────┘



  IDEAL: A Vercel-class deployment engine with auto-healing escalation, linked service provisioning, blue-green deploys, real-time streaming, and full API coverage for         
  remote/mobile management.                                                                                                                                                     
                                                                                                                                                                              
  Decisions Locked In                                              
                                                                                                                                                                                
  ┌─────────────────┬─────────────────────────────────────────────────────┐                                                                                                     
  │    Decision     │                       Choice                        │                                                                                                     
  ├─────────────────┼─────────────────────────────────────────────────────┤                                                                                                     
  │ Auto-healing    │ Escalating: restart → rebuild → rollback → alert    │                                                                                                     
  ├─────────────────┼─────────────────────────────────────────────────────┤                                                                                                     
  │ Linked services │ Postgres + Redis + MinIO bucket (Docker containers) │                                                                                                     
  ├─────────────────┼─────────────────────────────────────────────────────┤                                                                                                     
  │ PR previews     │ Design in data model now, build in Phase 2          │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Zero-downtime   │ Blue-green from day one (Traefik label swap)        │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Pipeline        │ Optional — local build + push always works          │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Background jobs │ ARQ (Redis-backed)                                  │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Build drivers   │ Per-site with global default                        │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Git providers   │ GitHub + GitLab (including self-hosted)             │
  ├─────────────────┼─────────────────────────────────────────────────────┤
  │ Scanning        │ Semgrep first, extensible for Fortify               │
  └─────────────────┴─────────────────────────────────────────────────────┘

  New Subsystems to Design

  1. Health Monitor + Auto-Healing Escalation

  Health Check Loop (ARQ cron, every 30s):

    For each running site:
      → Hit site.health_check_path
      → If 200: reset failure counter
      → If fail:
          failure_count++

          Level 1 (failures >= 3):   docker restart
          Level 2 (failures >= 6):   rebuild from last committed SHA
          Level 3 (failures >= 9):   rollback to previous deployment
          Level 4 (failures >= 12):  alert owner, mark site "degraded"

          Each level logs to HealthEvent table
          Each level sends notification

  class HealthEvent(Base):
      __tablename__ = "health_events"

      id          = Column(UUID, primary_key=True)
      site_id     = Column(UUID, ForeignKey("sites.id"))
      check_time  = Column(DateTime, default=utcnow)
      status_code = Column(Integer, nullable=True)    # HTTP status or null if timeout
      response_ms = Column(Integer, nullable=True)
      healthy     = Column(Boolean)
      action_taken = Column(String, nullable=True)    # "restart", "rebuild", "rollback", "alert"

  class Site(Base):
      # ... add fields ...
      health_failure_count  = Column(Integer, default=0)
      health_status         = Column(String, default="unknown")  # healthy, degraded, down
      last_health_check     = Column(DateTime, nullable=True)
      last_healthy_at       = Column(DateTime, nullable=True)

  2. Linked Services

  class LinkedService(Base):
      __tablename__ = "linked_services"

      id            = Column(UUID, primary_key=True)
      site_id       = Column(UUID, ForeignKey("sites.id"))
      tenant_id     = Column(UUID, ForeignKey("tenants.id"))

      service_type  = Column(String)    # "postgres", "redis", "minio_bucket"
      name          = Column(String)    # "my-app-db"
      container_id  = Column(String, nullable=True)
      status        = Column(String)    # "provisioning", "running", "stopped", "error"

      # Connection details (injected as env vars)
      connection_env = Column(JSONB)
      # e.g., {"DATABASE_URL": "postgresql://...", "PGHOST": "...", "PGPORT": "5432"}

      # Service-specific config
      config = Column(JSONB, default=dict)
      # Postgres: {"version": "16", "storage_size": "1Gi"}
      # Redis: {"maxmemory": "256mb"}
      # MinIO: {"bucket_name": "my-app-assets"}

      # Lifecycle
      delete_on_site_removal = Column(Boolean, default=False)  # safety default: keep data

  Provisioning flow:
  Site declares: linked_services = ["postgres", "minio_bucket"]

  Pipeline CLONE stage:
    → Check if linked services exist for this site
    → If postgres doesn't exist:
        → docker run postgres:16-alpine with auto-generated credentials
        → Store connection_env: DATABASE_URL, PGHOST, PGPORT, PGUSER, PGPASSWORD
        → Wait for healthcheck
    → Inject all connection_env vars into site's runtime_env automatically

  On site delete:
    → If delete_on_site_removal: remove service container + volume
    → Else: warn "orphaned service containers exist"

  3. Blue-Green Deploys

  Current (stop-start):
    stop old → start new → hope for the best

  Blue-Green:
    1. Start NEW container: ae-{tenant}-{workspace}-{site}-green
       (on a temporary port, no Traefik labels yet)
    2. Wait for health check to pass (up to 60s)
    3. If healthy:
       → Apply Traefik labels to GREEN container
       → Remove Traefik labels from BLUE (old) container
       → Stop BLUE container after 10s drain period
       → Rename GREEN to primary name
    4. If unhealthy:
       → Stop GREEN container
       → Keep BLUE running (no disruption)
       → Mark deploy as FAILED
       → Log: "New version failed health check, old version still serving"

  # New fields on Site model
  class Site(Base):
      # ... existing ...
      active_container_id   = Column(String, nullable=True)  # currently serving traffic
      pending_container_id  = Column(String, nullable=True)  # green container during deploy

  4. Real-Time Logs + Notifications

  # SSE endpoint for pipeline streaming
  @router.get("/api/v1/pipelines/{pipeline_id}/stream")
  async def stream_pipeline(pipeline_id: UUID):
      """Server-Sent Events stream of pipeline progress."""
      async def event_generator():
          async for event in subscribe_pipeline_events(pipeline_id):
              yield f"data: {json.dumps(event)}\n\n"
              # Events: stage_started, stage_log, stage_completed, pipeline_completed

      return StreamingResponse(event_generator(), media_type="text/event-stream")

  # Notification webhooks (site-level config)
  class NotificationConfig(Base):
      __tablename__ = "notification_configs"

      id       = Column(UUID, primary_key=True)
      site_id  = Column(UUID, ForeignKey("sites.id"))
      type     = Column(String)    # "webhook", "email", "slack"
      target   = Column(String)    # URL, email address, or Slack webhook URL
      events   = Column(JSONB)     # ["deploy_success", "deploy_failed", "health_degraded"]
      enabled  = Column(Boolean, default=True)

  5. Full API Coverage (Mobile-Ready)

  Every feature must be API-first. Here's the complete endpoint map:

  # Core Resources
  GET/POST   /api/v1/tenants
  GET/PATCH/DELETE /api/v1/tenants/{id}

  GET/POST   /api/v1/tenants/{id}/workspaces
  GET/PATCH/DELETE /api/v1/workspaces/{id}

  GET/POST   /api/v1/workspaces/{id}/sites
  GET/PATCH/DELETE /api/v1/sites/{id}

  # Pipeline & Deploys
  POST       /api/v1/sites/{id}/deploy          # trigger pipeline
  POST       /api/v1/sites/{id}/rollback/{ver}   # rollback to version
  GET        /api/v1/sites/{id}/pipelines        # list pipeline runs
  GET        /api/v1/pipelines/{id}              # pipeline detail + stages
  POST       /api/v1/pipelines/{id}/cancel       # cancel running pipeline
  POST       /api/v1/pipelines/{id}/retry        # retry failed pipeline
  GET        /api/v1/pipelines/{id}/stream       # SSE log stream

  # Container Lifecycle
  POST       /api/v1/sites/{id}/stop
  POST       /api/v1/sites/{id}/restart
  GET        /api/v1/sites/{id}/status           # container + health status
  GET        /api/v1/sites/{id}/logs             # container logs

  # Git Configuration
  PUT        /api/v1/sites/{id}/git-config       # provider, branch, auto-deploy
  POST       /api/v1/webhooks/github             # GitHub webhook receiver
  POST       /api/v1/webhooks/gitlab             # GitLab webhook receiver

  # Environment Variables
  GET/PUT    /api/v1/sites/{id}/env
  DELETE     /api/v1/sites/{id}/env/{key}

  # Linked Services
  GET/POST   /api/v1/sites/{id}/services         # list/provision linked services
  DELETE     /api/v1/sites/{id}/services/{svc_id} # remove linked service

  # Health & Monitoring
  GET        /api/v1/sites/{id}/health-history   # health check events
  GET        /api/v1/dashboard/status            # all sites health overview

  # Notifications
  GET/POST   /api/v1/sites/{id}/notifications    # notification config
  PATCH/DELETE /api/v1/notifications/{id}

  # Platform Admin
  GET/PUT    /api/v1/platform/settings           # global defaults
  GET        /api/v1/platform/build-drivers      # available build drivers
  GET        /api/v1/ports                       # port allocation table

  Updated Implementation Phases

  ┌───────┬──────────────────────────────┬────────────────────────────────────────────────────────────────────────────┐
  │ Phase │            Scope             │                              Key Deliverables                              │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1a    │ Data models + migrations     │ PipelineRun, PipelineStage, LinkedService, HealthEvent, NotificationConfig │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1b    │ ARQ worker + pipeline engine │ Background pipeline execution, stage orchestration                         │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1c    │ BuildDriver extraction       │ LocalDockerBuilder (extract from local_deploy.py)                          │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1d    │ Blue-green deploy            │ Start green → health check → label swap → drain blue                       │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1e    │ Health monitor               │ ARQ cron job, escalation ladder (restart → rebuild → rollback → alert)     │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 1f    │ Wire deploy endpoint         │ POST /deploy enqueues pipeline, returns immediately                        │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 2a    │ Git provider layer           │ GitHub + GitLab webhook receivers, PushEvent normalization                 │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 2b    │ Linked services              │ Provision Postgres/Redis/MinIO containers, inject connection env           │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 2c    │ Real-time streaming          │ SSE endpoint for pipeline logs                                             │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 2d    │ Notifications                │ Webhook/email/Slack on deploy events                                       │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 2e    │ PR preview design            │ Data model fields for preview deploys (build in Phase 3)                   │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 3a    │ Semgrep scan stage           │ ScanDriver + pipeline integration                                          │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 3b    │ Remote/cloud build drivers   │ RemoteBuildKit, GCP Cloud Build, AWS CodeBuild                             │
  ├───────┼──────────────────────────────┼────────────────────────────────────────────────────────────────────────────┤
  │ 3c    │ PR preview implementation    │ PR webhook → unique URL → auto-cleanup                                     │
  └───────┴──────────────────────────────┴────────────────────────────────────────────────────────────────────────────┘

  ---
  ━━━ ✅  V E R I F Y ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 6/7

  🎯 PRODUCTION READINESS CHECKLIST ═════════════════════════════════════════════
  │ Feature                    │ Vercel Has │ We've Designed │ Status     │
  ├────────────────────────────┼────────────┼────────────────┼────────────┤
  │ Git push → auto deploy     │ ✅         │ ✅             │ Designed   │
  │ Pipeline stages (scan/build)│ ✅         │ ✅             │ Designed   │
  │ Preview deployments (PR)   │ ✅         │ ✅ (Phase 2)   │ Designed   │
  │ Instant rollback           │ ✅         │ ✅             │ Designed   │
  │ Zero-downtime (blue-green) │ ✅         │ ✅             │ Designed   │
  │ Health checks + auto-heal  │ ✅         │ ✅             │ Designed   │
  │ Linked services            │ ✅         │ ✅             │ Designed   │
  │ Real-time deploy logs      │ ✅         │ ✅ (SSE)       │ Designed   │
  │ Notifications              │ ✅         │ ✅             │ Designed   │
  │ API-first (mobile-ready)   │ ✅         │ ✅             │ Designed   │
  │ Custom domains + SSL       │ ✅         │ ✅ (existing)  │ Built      │
  │ Build caching              │ ✅         │ ✅ (BuildKit)  │ Designed   │
  │ Multi-provider (GH + GL)   │ ❌ (GH only)│ ✅            │ Designed   │
  │ Self-hosted git support    │ ❌         │ ✅             │ Designed   │
  │ Pluggable build backends   │ ❌         │ ✅             │ Designed   │
  │ Code scanning              │ ❌         │ ✅ (Semgrep)   │ Designed   │
  │ Local build path           │ ❌         │ ✅             │ Designed   │
  └────────────────────────────┴────────────┴────────────────┴────────────┘

  ━━━ 📚  L E A R N ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 7/7

  📋 SUMMARY: Closed all production-grade gaps — escalating auto-heal, linked service provisioning (Postgres/Redis/MinIO), blue-green deploys, SSE log streaming, notification
  system, and full mobile-ready API surface. The design now covers or exceeds Vercel's feature set across 17 dimensions.

  📁 CAPTURE: The four features that differentiate this from Vercel: multi-provider git (GitHub + GitLab + self-hosted), pluggable build backends, code scanning pipeline, and
  self-hosted with full data ownership.

  ➡️  NEXT: If you're satisfied with the design, say the word and I'll start with Phase 1a — writing the Alembic migration and SQLAlchemy models for PipelineRun, PipelineStage,
  LinkedService, HealthEvent, and NotificationConfig. That's the foundation everything else builds on.

  🗣️  Kairos: Design is complete — 17 feature dimensions covered, exceeding Vercel. Ready to start building Phase 1a on your go.



  RBAC Design for Adhara Engine

  Architecture Decision: Zitadel for Identity, Adhara for Authorization

  Zitadel handles:              Adhara Engine handles:
    ✅ Who is this person?         ✅ What can they access?
    ✅ Are their credentials valid? ✅ What role do they have on resource X?
    ✅ OIDC/JWT issuance           ✅ Permission checks per endpoint
    ✅ Password management         ✅ Membership management
    ✅ MFA                         ✅ API token scoping

  Why not Zitadel roles for everything? Zitadel's project roles are flat — admin or user globally. It can't express "admin of Tenant A, viewer of Workspace B in Tenant C." We
  need resource-scoped memberships in our own database.

  ---
  Role Hierarchy

  PLATFORM level
    └── platform_admin          Can do everything across all tenants
    └── platform_viewer         Can see all tenants (support/monitoring)

  TENANT level
    └── tenant_owner            Full control of tenant + all workspaces/sites
    └── tenant_admin            Manage workspaces, users, settings
    └── tenant_member           View tenant, access assigned workspaces

  WORKSPACE level
    └── workspace_admin         Full control of workspace + all sites
    └── workspace_deployer      Deploy, restart, rollback sites
    └── workspace_viewer        View sites, logs, status (read-only)

  SITE level (optional override)
    └── site_admin              Full control of one specific site
    └── site_deployer           Deploy/restart one specific site
    └── site_viewer             View one specific site

  Permission Matrix

                            platform  tenant  tenant  tenant  ws      ws        ws       site    site     site
  Action                    admin     owner   admin   member  admin   deployer  viewer   admin   deployer viewer
  ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
  Create tenant              ✅       ─       ─       ─       ─       ─         ─        ─       ─        ─
  Delete tenant              ✅       ✅      ─       ─       ─       ─         ─        ─       ─        ─
  Manage tenant members      ✅       ✅      ✅      ─       ─       ─         ─        ─       ─        ─
  View tenant                ✅       ✅      ✅      ✅      ─       ─         ─        ─       ─        ─

  Create workspace           ✅       ✅      ✅      ─       ─       ─         ─        ─       ─        ─
  Delete workspace           ✅       ✅      ✅      ─       ✅      ─         ─        ─       ─        ─
  Manage workspace members   ✅       ✅      ✅      ─       ✅      ─         ─        ─       ─        ─
  View workspace             ✅       ✅      ✅      ✅      ✅      ✅        ✅       ─       ─        ─

  Create site                ✅       ✅      ✅      ─       ✅      ─         ─        ─       ─        ─
  Delete site                ✅       ✅      ✅      ─       ✅      ─         ─        ✅      ─        ─
  Deploy / rollback          ✅       ✅      ✅      ─       ✅      ✅        ─        ✅      ✅       ─
  Stop / restart             ✅       ✅      ✅      ─       ✅      ✅        ─        ✅      ✅       ─
  Configure env vars         ✅       ✅      ✅      ─       ✅      ✅        ─        ✅      ✅       ─
  View site / logs           ✅       ✅      ✅      ✅      ✅      ✅        ✅       ✅      ✅       ✅
  Manage linked services     ✅       ✅      ✅      ─       ✅      ─         ─        ✅      ─        ─
  Configure git/webhooks     ✅       ✅      ✅      ─       ✅      ─         ─        ✅      ─        ─
  Configure notifications    ✅       ✅      ✅      ─       ✅      ✅        ─        ✅      ✅       ─

  Manage platform settings   ✅       ─       ─       ─       ─       ─         ─        ─       ─        ─
  View all health/dashboard  ✅       ✅      ✅      ─       ✅      ✅        ✅       ─       ─        ─

  ---
  Data Models

  class Membership(Base):
      """Links a user to a resource with a role. This is THE authorization table."""
      __tablename__ = "memberships"

      id          = Column(UUID, primary_key=True, default=uuid4)

      # Who
      user_id     = Column(String, nullable=False)     # Zitadel user ID (from JWT "sub" claim)
      user_email  = Column(String, nullable=False)     # Denormalized for display/search

      # What resource (exactly one of these is set)
      resource_type = Column(String, nullable=False)   # "platform", "tenant", "workspace", "site"
      resource_id   = Column(UUID, nullable=True)      # null for platform-level roles

      # What role
      role        = Column(String, nullable=False)     # "tenant_owner", "workspace_deployer", etc.

      # Metadata
      granted_by  = Column(String, nullable=True)      # user_id of who granted this
      granted_at  = Column(DateTime, default=utcnow)
      expires_at  = Column(DateTime, nullable=True)    # optional expiry for contractors/temp access

      # Constraints
      __table_args__ = (
          UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_membership"),
          Index("ix_membership_user", "user_id"),
          Index("ix_membership_resource", "resource_type", "resource_id"),
      )


  class APIToken(Base):
      """Scoped API tokens for service accounts, CI/CD, mobile apps."""
      __tablename__ = "api_tokens"

      id           = Column(UUID, primary_key=True, default=uuid4)

      # Who owns this token
      user_id      = Column(String, nullable=False)
      name         = Column(String, nullable=False)    # "CI Deploy Token", "Mobile App"

      # The token itself (hashed, never stored in plaintext after creation)
      token_hash   = Column(String, nullable=False)
      token_prefix = Column(String, nullable=False)    # "ae_...abc" for identification

      # Scope — what can this token access?
      scopes       = Column(JSONB, nullable=False)
      # e.g., [
      #   {"resource_type": "workspace", "resource_id": "uuid", "permissions": ["deploy", "restart"]},
      #   {"resource_type": "site", "resource_id": "uuid", "permissions": ["view", "logs"]}
      # ]

      # Lifecycle
      created_at   = Column(DateTime, default=utcnow)
      expires_at   = Column(DateTime, nullable=True)
      last_used_at = Column(DateTime, nullable=True)
      revoked      = Column(Boolean, default=False)
      revoked_at   = Column(DateTime, nullable=True)

  ---
  Authorization Middleware

  # api/app/core/permissions.py

  from enum import Enum

  class Permission(str, Enum):
      """Fine-grained permissions checked at the endpoint level."""
      # Tenant
      TENANT_CREATE       = "tenant:create"
      TENANT_DELETE       = "tenant:delete"
      TENANT_UPDATE       = "tenant:update"
      TENANT_VIEW         = "tenant:view"
      TENANT_MANAGE_MEMBERS = "tenant:manage_members"

      # Workspace
      WORKSPACE_CREATE    = "workspace:create"
      WORKSPACE_DELETE    = "workspace:delete"
      WORKSPACE_UPDATE    = "workspace:update"
      WORKSPACE_VIEW      = "workspace:view"
      WORKSPACE_MANAGE_MEMBERS = "workspace:manage_members"

      # Site
      SITE_CREATE         = "site:create"
      SITE_DELETE         = "site:delete"
      SITE_UPDATE         = "site:update"
      SITE_VIEW           = "site:view"
      SITE_DEPLOY         = "site:deploy"
      SITE_STOP           = "site:stop"
      SITE_RESTART        = "site:restart"
      SITE_ROLLBACK       = "site:rollback"
      SITE_LOGS           = "site:logs"
      SITE_ENV            = "site:env"
      SITE_SERVICES       = "site:services"
      SITE_GIT_CONFIG     = "site:git_config"
      SITE_NOTIFICATIONS  = "site:notifications"

      # Platform
      PLATFORM_SETTINGS   = "platform:settings"
      PLATFORM_DASHBOARD  = "platform:dashboard"


  # Role → permissions mapping
  ROLE_PERMISSIONS: dict[str, set[Permission]] = {
      "platform_admin": set(Permission),  # all permissions

      "tenant_owner": {
          Permission.TENANT_DELETE, Permission.TENANT_UPDATE, Permission.TENANT_VIEW,
          Permission.TENANT_MANAGE_MEMBERS,
          Permission.WORKSPACE_CREATE, Permission.WORKSPACE_DELETE, Permission.WORKSPACE_UPDATE,
          Permission.WORKSPACE_VIEW, Permission.WORKSPACE_MANAGE_MEMBERS,
          Permission.SITE_CREATE, Permission.SITE_DELETE, Permission.SITE_UPDATE,
          Permission.SITE_VIEW, Permission.SITE_DEPLOY, Permission.SITE_STOP,
          Permission.SITE_RESTART, Permission.SITE_ROLLBACK, Permission.SITE_LOGS,
          Permission.SITE_ENV, Permission.SITE_SERVICES, Permission.SITE_GIT_CONFIG,
          Permission.SITE_NOTIFICATIONS,
          Permission.PLATFORM_DASHBOARD,
      },

      "tenant_admin": {
          Permission.TENANT_UPDATE, Permission.TENANT_VIEW, Permission.TENANT_MANAGE_MEMBERS,
          Permission.WORKSPACE_CREATE, Permission.WORKSPACE_DELETE, Permission.WORKSPACE_UPDATE,
          Permission.WORKSPACE_VIEW, Permission.WORKSPACE_MANAGE_MEMBERS,
          Permission.SITE_CREATE, Permission.SITE_DELETE, Permission.SITE_UPDATE,
          Permission.SITE_VIEW, Permission.SITE_DEPLOY, Permission.SITE_STOP,
          Permission.SITE_RESTART, Permission.SITE_ROLLBACK, Permission.SITE_LOGS,
          Permission.SITE_ENV, Permission.SITE_SERVICES, Permission.SITE_GIT_CONFIG,
          Permission.SITE_NOTIFICATIONS,
          Permission.PLATFORM_DASHBOARD,
      },

      "tenant_member": {
          Permission.TENANT_VIEW,
          Permission.WORKSPACE_VIEW,
          Permission.SITE_VIEW, Permission.SITE_LOGS,
      },

      "workspace_admin": {
          Permission.WORKSPACE_DELETE, Permission.WORKSPACE_UPDATE, Permission.WORKSPACE_VIEW,
          Permission.WORKSPACE_MANAGE_MEMBERS,
          Permission.SITE_CREATE, Permission.SITE_DELETE, Permission.SITE_UPDATE,
          Permission.SITE_VIEW, Permission.SITE_DEPLOY, Permission.SITE_STOP,
          Permission.SITE_RESTART, Permission.SITE_ROLLBACK, Permission.SITE_LOGS,
          Permission.SITE_ENV, Permission.SITE_SERVICES, Permission.SITE_GIT_CONFIG,
          Permission.SITE_NOTIFICATIONS,
          Permission.PLATFORM_DASHBOARD,
      },

      "workspace_deployer": {
          Permission.WORKSPACE_VIEW,
          Permission.SITE_VIEW, Permission.SITE_DEPLOY, Permission.SITE_STOP,
          Permission.SITE_RESTART, Permission.SITE_ROLLBACK, Permission.SITE_LOGS,
          Permission.SITE_ENV, Permission.SITE_NOTIFICATIONS,
          Permission.PLATFORM_DASHBOARD,
      },

      "workspace_viewer": {
          Permission.WORKSPACE_VIEW,
          Permission.SITE_VIEW, Permission.SITE_LOGS,
          Permission.PLATFORM_DASHBOARD,
      },

      "site_admin": {
          Permission.SITE_DELETE, Permission.SITE_UPDATE, Permission.SITE_VIEW,
          Permission.SITE_DEPLOY, Permission.SITE_STOP, Permission.SITE_RESTART,
          Permission.SITE_ROLLBACK, Permission.SITE_LOGS, Permission.SITE_ENV,
          Permission.SITE_SERVICES, Permission.SITE_GIT_CONFIG, Permission.SITE_NOTIFICATIONS,
      },

      "site_deployer": {
          Permission.SITE_VIEW, Permission.SITE_DEPLOY, Permission.SITE_STOP,
          Permission.SITE_RESTART, Permission.SITE_ROLLBACK, Permission.SITE_LOGS,
          Permission.SITE_ENV, Permission.SITE_NOTIFICATIONS,
      },

      "site_viewer": {
          Permission.SITE_VIEW, Permission.SITE_LOGS,
      },
  }

  The Authorization Check Function

  # api/app/core/authorize.py

  async def authorize(
      user: dict,               # JWT claims from require_auth
      permission: Permission,   # what they're trying to do
      resource_type: str,        # "tenant", "workspace", "site"
      resource_id: UUID,         # which specific resource
      db: Session,
  ) -> None:
      """
      Check if user has permission on a resource.
      Walks UP the hierarchy: site → workspace → tenant → platform.
      Raises 403 if denied.
      """
      user_id = user["sub"]

      # Build the resource chain for hierarchical lookup
      # e.g., for a site: check site membership, then workspace, then tenant, then platform
      resource_chain = await build_resource_chain(db, resource_type, resource_id)
      # Returns: [
      #   ("site", site_id),
      #   ("workspace", workspace_id),
      #   ("tenant", tenant_id),
      #   ("platform", None),
      # ]

      # Check each level — first match wins (most specific first)
      for res_type, res_id in resource_chain:
          membership = await get_membership(db, user_id, res_type, res_id)
          if membership:
              role_perms = ROLE_PERMISSIONS.get(membership.role, set())
              if permission in role_perms:
                  # Check expiry
                  if membership.expires_at and membership.expires_at < utcnow():
                      continue  # expired, check next level
                  return  # AUTHORIZED

      raise HTTPException(
          status_code=403,
          detail=f"You don't have {permission.value} permission on this {resource_type}"
      )


  async def build_resource_chain(db: Session, resource_type: str, resource_id: UUID):
      """Walk up: site → workspace → tenant → platform."""
      chain = []

      if resource_type == "site":
          site = await get_site(db, resource_id)
          chain.append(("site", resource_id))
          chain.append(("workspace", site.workspace_id))
          chain.append(("tenant", site.tenant_id))
      elif resource_type == "workspace":
          ws = await get_workspace(db, resource_id)
          chain.append(("workspace", resource_id))
          chain.append(("tenant", ws.tenant_id))
      elif resource_type == "tenant":
          chain.append(("tenant", resource_id))

      chain.append(("platform", None))  # always check platform-level last
      return chain

  Usage on Endpoints

  # api/app/routers/deployments.py

  @router.post("/api/v1/sites/{site_id}/deploy")
  async def deploy_site(
      site_id: UUID,
      user: dict = Depends(require_auth),
      db: Session = Depends(get_db),
  ):
      await authorize(user, Permission.SITE_DEPLOY, "site", site_id, db)
      # ... proceed with deployment

  Every endpoint gets one line of authorization. Clean.

  ---
  Revocation Flow (Employee Leaves)

  Admin removes user from tenant:
    DELETE /api/v1/tenants/{id}/members/{user_id}
      → Deletes Membership row for tenant
      → CASCADE: also deletes workspace + site memberships under that tenant
      → User's next API call → 403 (immediate, no token refresh needed)
      → Optional: also revoke in Zitadel (disable user account) for full lockout

  # Cascade delete memberships when removing from tenant
  async def remove_tenant_member(db: Session, tenant_id: UUID, user_id: str):
      """Remove user from tenant and ALL nested resources."""
      # Get all workspace IDs under this tenant
      workspace_ids = await get_workspace_ids_for_tenant(db, tenant_id)
      # Get all site IDs under these workspaces
      site_ids = await get_site_ids_for_workspaces(db, workspace_ids)

      # Delete all memberships for this user under this tenant tree
      await db.execute(
          delete(Membership).where(
              Membership.user_id == user_id,
              or_(
                  and_(Membership.resource_type == "tenant", Membership.resource_id == tenant_id),
                  and_(Membership.resource_type == "workspace", Membership.resource_id.in_(workspace_ids)),
                  and_(Membership.resource_type == "site", Membership.resource_id.in_(site_ids)),
              )
          )
      )
      await db.commit()

  Instant revocation — because we check the memberships table on every API call (not JWT claims), deleting the membership row takes effect immediately. No need to wait for
  token expiry.

  ---
  API Tokens (for Mobile, CI/CD, Service Accounts)

  # Token format: ae_live_<random_32_chars>
  # Only shown ONCE at creation, then stored as SHA-256 hash

  @router.post("/api/v1/tokens")
  async def create_api_token(
      request: TokenCreateRequest,
      user: dict = Depends(require_auth),
      db: Session = Depends(get_db),
  ):
      """Create a scoped API token. The plain token is only returned once."""
      raw_token = f"ae_live_{secrets.token_urlsafe(32)}"
      token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

      # Validate that user actually has the permissions they're granting
      for scope in request.scopes:
          for perm in scope.permissions:
              await authorize(user, perm, scope.resource_type, scope.resource_id, db)

      api_token = APIToken(
          user_id=user["sub"],
          name=request.name,
          token_hash=token_hash,
          token_prefix=raw_token[:12],
          scopes=request.scopes,
          expires_at=request.expires_at,
      )
      db.add(api_token)
      await db.commit()

      return {"token": raw_token, "id": api_token.id}  # raw_token shown only once

  API tokens are authenticated via Authorization: Bearer ae_live_... — the auth middleware detects the ae_ prefix and looks up the hash in the database instead of validating as
   a JWT.

  ---
  Membership Management Endpoints

  # Tenant members
  GET    /api/v1/tenants/{id}/members          # List members + roles
  POST   /api/v1/tenants/{id}/members          # Invite user (email + role)
  PATCH  /api/v1/tenants/{id}/members/{uid}    # Change role
  DELETE /api/v1/tenants/{id}/members/{uid}    # Remove (cascading)

  # Workspace members
  GET    /api/v1/workspaces/{id}/members
  POST   /api/v1/workspaces/{id}/members
  PATCH  /api/v1/workspaces/{id}/members/{uid}
  DELETE /api/v1/workspaces/{id}/members/{uid}

  # Site members (optional granular access)
  GET    /api/v1/sites/{id}/members
  POST   /api/v1/sites/{id}/members
  PATCH  /api/v1/sites/{id}/members/{uid}
  DELETE /api/v1/sites/{id}/members/{uid}

  # API Tokens
  GET    /api/v1/tokens                         # List my tokens
  POST   /api/v1/tokens                         # Create scoped token
  DELETE /api/v1/tokens/{id}                    # Revoke token

  ---
  How This Fits in the Build Phases

  ┌───────┬──────────────────────────────────────────────────────────────┐
  │ Phase │                          RBAC Work                           │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1a    │ Membership + APIToken models, Alembic migration              │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1b    │ Permission enum, ROLE_PERMISSIONS map, authorize() function  │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1c    │ Auth middleware update — support both JWT and ae_ API tokens │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1d    │ Wire authorize() into ALL existing endpoints                 │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1e    │ Membership CRUD endpoints (tenant/workspace/site members)    │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 1f    │ API token CRUD endpoints                                     │
  ├───────┼──────────────────────────────────────────────────────────────┤
  │ 2+    │ UI for member management, role picker, token creation        │
  └───────┴──────────────────────────────────────────────────────────────┘


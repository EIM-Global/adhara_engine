const BASE_URL = '/api/v1';

// ── Auth token integration ──────────────────────────────────
let _getToken: (() => string | undefined) | null = null;

export function setTokenGetter(fn: (() => string | undefined) | null) {
  _getToken = fn;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = _getToken?.();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    // No token yet — reject early so react-query retries when auth is ready
    throw new Error('Not authenticated');
  }
  const opts: RequestInit = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE_URL}${path}`, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return {} as T;
  return res.json();
}

// ── Types ────────────────────────────────────────────────────

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  owner_email: string;
  created_at: string;
}

export interface Workspace {
  id: string;
  tenant_id: string;
  name: string;
  slug: string;
  adhara_api_url?: string;
  created_at: string;
}

export interface Site {
  id: string;
  workspace_id: string;
  tenant_id: string;
  name: string;
  slug: string;
  source_type: string;
  source_url?: string;
  dockerfile_path?: string;
  build_command?: string;
  container_port: number;
  host_port?: number;
  deploy_target: string;
  custom_domains: string[];
  runtime_env: Record<string, string>;
  build_env: Record<string, string>;
  health_check_path: string;
  status: string;
  current_deployment_id?: string;
  // Git follow
  git_provider?: string;
  git_provider_url?: string;
  git_branch?: string;
  auto_deploy: boolean;
  webhook_secret?: string;
  last_deployed_sha?: string;
  git_token_username?: string;
  git_token?: string;
  // Build config
  build_driver?: string;
  scan_enabled: boolean;
  scan_fail_on?: string;
  // Health
  health_failure_count: number;
  health_status?: string;
  last_health_check?: string;
  last_healthy_at?: string;
  health_auto_remediate?: boolean;
  // Blue-green
  active_container_id?: string;
  pending_container_id?: string;
  created_at: string;
}

export interface Deployment {
  id: string;
  site_id: string;
  version: number;
  status: string;
  image_tag?: string;
  host_port?: number;
  container_port?: number;
  build_logs?: string;
  deploy_logs?: string;
  created_at: string;
  deployed_at?: string;
}

export interface ContainerStatus {
  container_id?: string;
  name: string;
  status: string;
  image?: string;
  ports?: Record<string, unknown>;
}

export interface EnvResponse {
  runtime_env: Record<string, string>;
  build_env: Record<string, string>;
  warning?: string;
}

export interface DNSRecord {
  type: string;
  name: string;
  value: string;
  purpose: string;
}

export interface DomainResponse {
  domain: string;
  is_platform: boolean;
  verified: boolean;
  dns_records: DNSRecord[];
  verification_token?: string;
}

export interface SiteSummary {
  id: string;
  name: string;
  slug: string;
  status: string;
  host_port: number | null;
  tenant_slug: string;
  workspace_slug: string;
}

export interface ServiceCredentials {
  username: string;
  password: string | null;
}

export interface ServiceInfo {
  name: string;
  container_name: string;
  display_name: string;
  description: string;
  icon: string;
  category: string;
  status: string;
  health: string | null;
  image: string;
  ports: Record<string, string>;
  management_url: string | null;
  management_label: string | null;
  credentials: ServiceCredentials | null;
  started_at: string | null;
}

// ── Pipeline Types ──────────────────────────────────────────

export interface PipelineStage {
  id: string;
  pipeline_run_id: string;
  name: string;
  order: number;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  logs?: string;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface PipelineRun {
  id: string;
  site_id: string;
  tenant_id: string;
  trigger: string;
  git_provider?: string;
  git_ref?: string;
  commit_sha?: string;
  commit_message?: string;
  commit_author?: string;
  status: string;
  build_driver?: string;
  image_ref?: string;
  deployment_id?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
  triggered_by?: string;
  stages: PipelineStage[];
}

export interface PipelineRunSummary {
  id: string;
  site_id: string;
  trigger: string;
  status: string;
  commit_sha?: string;
  commit_message?: string;
  created_at: string;
  started_at?: string;
  finished_at?: string;
}

// ── Membership Types ────────────────────────────────────────

export interface Membership {
  id: string;
  user_id: string;
  user_email: string;
  resource_type: string;
  resource_id: string;
  role: string;
  expires_at?: string;
  created_at: string;
}

// ── API Token Types ─────────────────────────────────────────

export interface APIToken {
  id: string;
  name: string;
  token_prefix: string;
  scopes: TokenScope[];
  created_at: string;
  expires_at?: string;
  last_used_at?: string;
  revoked: boolean;
}

export interface APITokenCreateResponse extends APIToken {
  token: string;
}

export interface TokenScope {
  resource_type: string;
  resource_id: string;
  permissions: string[];
}

// ── Health Types ────────────────────────────────────────────

export interface HealthEvent {
  id: string;
  site_id: string;
  check_time: string;
  status_code?: number;
  response_ms?: number;
  healthy: boolean;
  action_taken?: string;
}

export interface HealthSummary {
  site_id: string;
  site_slug: string;
  health_status?: string;
  health_failure_count: number;
  last_health_check?: string;
  last_healthy_at?: string;
  recent_events: HealthEvent[];
}

// ── Linked Service Types ────────────────────────────────────

export interface LinkedService {
  id: string;
  site_id: string;
  service_type: string;
  name?: string;
  container_id?: string;
  connection_env: Record<string, string>;
  status: string;
  delete_on_site_removal: boolean;
  created_at: string;
}

// ── Notification Types ──────────────────────────────────────

export interface NotificationConfig {
  id: string;
  site_id: string;
  type: string;
  target: string;
  name?: string;
  events: string[];
  enabled: boolean;
  created_at: string;
}

// ── Preview Types ───────────────────────────────────────────

export interface PreviewEnvironment {
  id: string;
  site_id: string;
  pr_number: number;
  pr_title?: string;
  pr_author?: string;
  pr_branch: string;
  pr_url?: string;
  git_provider: string;
  commit_sha?: string;
  pipeline_run_id?: string;
  status: string;
  host_port?: number;
  preview_url?: string;
  image_tag?: string;
  ttl_hours: number;
  pr_state: string;
  destroy_reason?: string;
  created_at: string;
  updated_at?: string;
  destroyed_at?: string;
}

// ── Registry Types ──────────────────────────────────────────

export interface RegistryRepo {
  repository: string;
  tags: string[];
  site_id?: string;
  site_name?: string;
  site_slug?: string;
  tenant_slug?: string;
  workspace_slug?: string;
}

export interface RegistryResponse {
  repositories: RegistryRepo[];
  error?: string;
}

export interface TagDetail {
  tag: string;
  digest: string;
  size: number;
  created?: string;
  architecture?: string;
  layers: number;
}

export interface RepoDetail extends RegistryRepo {
  tag_details: TagDetail[];
}

export interface RegistryHealth {
  reachable: boolean;
  repository_count: number;
  total_tags: number;
  error?: string;
}

// ── Driver Info ─────────────────────────────────────────────

export interface EnvVarStatus {
  name: string;
  is_set: boolean;
}

export interface DriverInfo {
  name: string;
  is_default: boolean;
  description: string;
  status: 'ready' | 'not_configured' | 'unavailable';
  required_env: EnvVarStatus[];
  setup_hint: string;
}

export interface PlatformConfig {
  platform_domain: string;
  engine_public_ip: string;
  registry_host: string;
}

// ── API ──────────────────────────────────────────────────────

export const api = {
  // All Sites (sidebar)
  listAllSites: () => request<SiteSummary[]>('GET', '/sites'),

  // Tenants
  listTenants: () => request<Tenant[]>('GET', '/tenants'),
  getTenant: (id: string) => request<Tenant>('GET', `/tenants/${id}`),
  createTenant: (data: { name: string; owner_email: string; plan?: string }) =>
    request<Tenant>('POST', '/tenants', data),
  deleteTenant: (id: string) => request<void>('DELETE', `/tenants/${id}`),

  // Workspaces
  listWorkspaces: (tenantId: string) => request<Workspace[]>('GET', `/tenants/${tenantId}/workspaces`),
  getWorkspace: (id: string) => request<Workspace>('GET', `/workspaces/${id}`),
  createWorkspace: (tenantId: string, data: { name: string; adhara_api_url?: string; adhara_api_key?: string }) =>
    request<Workspace>('POST', `/tenants/${tenantId}/workspaces`, data),
  deleteWorkspace: (id: string) => request<void>('DELETE', `/workspaces/${id}`),

  // Sites
  listSites: (workspaceId: string) => request<Site[]>('GET', `/workspaces/${workspaceId}/sites`),
  getSite: (id: string) => request<Site>('GET', `/sites/${id}`),
  createSite: (workspaceId: string, data: Partial<Site>) =>
    request<Site>('POST', `/workspaces/${workspaceId}/sites`, data),
  updateSite: (id: string, data: Partial<Site>) =>
    request<Site>('PATCH', `/sites/${id}`, data),
  deleteSite: (id: string) => request<void>('DELETE', `/sites/${id}`),

  // Deployments
  deploySite: (siteId: string) => request<{ pipeline_run_id: string }>('POST', `/sites/${siteId}/deploy`),
  stopSite: (siteId: string) => request<void>('POST', `/sites/${siteId}/stop`),
  restartSite: (siteId: string) => request<void>('POST', `/sites/${siteId}/restart`),
  getSiteLogs: (siteId: string, tail = 100) =>
    request<{ lines: string[] }>('GET', `/sites/${siteId}/logs?tail=${tail}`),
  getSiteStatus: (siteId: string) => request<ContainerStatus>('GET', `/sites/${siteId}/status`),
  listDeployments: (siteId: string) => request<Deployment[]>('GET', `/sites/${siteId}/deployments`),

  // Pipelines
  listPipelines: (siteId: string) => request<PipelineRunSummary[]>('GET', `/sites/${siteId}/pipelines`),
  getPipeline: (id: string) => request<PipelineRun>('GET', `/pipelines/${id}`),
  cancelPipeline: (id: string) => request<void>('POST', `/pipelines/${id}/cancel`),
  retryPipeline: (id: string) => request<{ pipeline_run_id: string }>('POST', `/pipelines/${id}/retry`),
  cancelPendingPipelines: (siteId: string) => request<{ cancelled: number }>('POST', `/sites/${siteId}/pipelines/cancel-pending`),
  clearPipelineHistory: (siteId: string) => request<{ deleted: number }>('DELETE', `/sites/${siteId}/pipelines/completed`),

  // Env
  getEnv: (siteId: string) => request<EnvResponse>('GET', `/sites/${siteId}/env`),
  setEnv: (siteId: string, vars: { key: string; value: string; scope: string }[]) =>
    request<EnvResponse>('PUT', `/sites/${siteId}/env`, { vars }),
  deleteEnv: (siteId: string, key: string) => request<EnvResponse>('DELETE', `/sites/${siteId}/env/${key}`),

  // Domains
  listDomains: (siteId: string) => request<DomainResponse[]>('GET', `/sites/${siteId}/domains`),
  addDomain: (siteId: string, domain: string) =>
    request<DomainResponse>('POST', `/sites/${siteId}/domains`, { domain }),
  removeDomain: (siteId: string, domain: string) =>
    request<void>('DELETE', `/sites/${siteId}/domains/${domain}`),
  verifyDomain: (siteId: string, domain: string) =>
    request<DomainResponse>('POST', `/sites/${siteId}/domains/${domain}/verify`),

  // Members
  listTenantMembers: (tenantId: string) => request<Membership[]>('GET', `/tenants/${tenantId}/members`),
  addTenantMember: (tenantId: string, data: { user_id: string; user_email: string; role: string }) =>
    request<Membership>('POST', `/tenants/${tenantId}/members`, data),
  updateTenantMember: (tenantId: string, userId: string, data: { role: string }) =>
    request<Membership>('PATCH', `/tenants/${tenantId}/members/${userId}`, data),
  removeTenantMember: (tenantId: string, userId: string) =>
    request<void>('DELETE', `/tenants/${tenantId}/members/${userId}`),

  listWorkspaceMembers: (wsId: string) => request<Membership[]>('GET', `/workspaces/${wsId}/members`),
  addWorkspaceMember: (wsId: string, data: { user_id: string; user_email: string; role: string }) =>
    request<Membership>('POST', `/workspaces/${wsId}/members`, data),
  updateWorkspaceMember: (wsId: string, userId: string, data: { role: string }) =>
    request<Membership>('PATCH', `/workspaces/${wsId}/members/${userId}`, data),
  removeWorkspaceMember: (wsId: string, userId: string) =>
    request<void>('DELETE', `/workspaces/${wsId}/members/${userId}`),

  listSiteMembers: (siteId: string) => request<Membership[]>('GET', `/sites/${siteId}/members`),
  addSiteMember: (siteId: string, data: { user_id: string; user_email: string; role: string }) =>
    request<Membership>('POST', `/sites/${siteId}/members`, data),
  updateSiteMember: (siteId: string, userId: string, data: { role: string }) =>
    request<Membership>('PATCH', `/sites/${siteId}/members/${userId}`, data),
  removeSiteMember: (siteId: string, userId: string) =>
    request<void>('DELETE', `/sites/${siteId}/members/${userId}`),

  // API Tokens
  listTokens: () => request<APIToken[]>('GET', '/tokens'),
  createToken: (data: { name: string; scopes?: TokenScope[]; expires_at?: string }) =>
    request<APITokenCreateResponse>('POST', '/tokens', data),
  revokeToken: (id: string) => request<void>('DELETE', `/tokens/${id}`),

  // Health
  getHealthHistory: (siteId: string) => request<HealthSummary>('GET', `/sites/${siteId}/health-history`),

  // Linked Services
  listLinkedServices: (siteId: string) => request<LinkedService[]>('GET', `/sites/${siteId}/linked-services`),
  createLinkedService: (siteId: string, data: { service_type: string; name?: string }) =>
    request<LinkedService>('POST', `/sites/${siteId}/linked-services`, data),
  deleteLinkedService: (siteId: string, serviceId: string) =>
    request<void>('DELETE', `/sites/${siteId}/linked-services/${serviceId}`),

  // Notifications
  listNotifications: (siteId: string) => request<NotificationConfig[]>('GET', `/sites/${siteId}/notifications`),
  createNotification: (siteId: string, data: { type: string; target: string; name?: string; events?: string[] }) =>
    request<NotificationConfig>('POST', `/sites/${siteId}/notifications`, data),
  updateNotification: (id: string, data: Partial<NotificationConfig>) =>
    request<NotificationConfig>('PATCH', `/notifications/${id}`, data),
  deleteNotification: (id: string) => request<void>('DELETE', `/notifications/${id}`),

  // Previews
  listPreviews: (siteId: string) => request<PreviewEnvironment[]>('GET', `/sites/${siteId}/previews`),
  getPreview: (id: string) => request<PreviewEnvironment>('GET', `/previews/${id}`),
  createPreview: (siteId: string, data: { pr_number: number; pr_branch: string; commit_sha: string; git_provider: string; pr_title?: string }) =>
    request<PreviewEnvironment>('POST', `/sites/${siteId}/previews`, data),
  deletePreview: (id: string) => request<void>('DELETE', `/previews/${id}`),

  // Registry Images
  listSiteImages: (siteId: string) =>
    request<{ repository: string; tags: string[]; error?: string }>('GET', `/sites/${siteId}/images`),

  // Registry
  listRegistry: () => request<RegistryResponse>('GET', '/registry'),
  getRegistryRepo: (repo: string) => request<RegistryRepo>('GET', `/registry/${repo}`),
  getRegistryRepoDetail: (repo: string) => request<RepoDetail>('GET', `/registry/${repo}/detail`),
  deleteRegistryTag: (repo: string, tag: string) => request<{ status: string }>('DELETE', `/registry/${repo}/tags/${tag}`),
  deleteRegistryRepo: (repo: string) => request<{ status: string; deleted_tags: number }>('DELETE', `/registry/${repo}`),
  getRegistryHealth: () => request<RegistryHealth>('GET', '/registry/health'),

  // Platform
  listBuildDrivers: () => request<DriverInfo[]>('GET', '/platform/build-drivers'),
  listScanDrivers: () => request<DriverInfo[]>('GET', '/platform/scan-drivers'),
  getPlatformConfig: () => request<PlatformConfig>('GET', '/platform/config'),
  updatePlatformConfig: (data: Partial<PlatformConfig>) => request<PlatformConfig>('PATCH', '/platform/config', data),

  // Ports
  listPorts: () => request<unknown[]>('GET', '/ports'),

  // Services
  listServices: () => request<{ services: ServiceInfo[] }>('GET', '/services'),
  getServiceLogs: (name: string, tail = 200) =>
    request<{ service: string; lines: string[] }>('GET', `/services/${name}/logs?tail=${tail}`),
  restartService: (name: string) => request<{ status: string }>('POST', `/services/${name}/restart`),

  // Health check
  health: () => fetch('/health').then(r => r.json()),
};

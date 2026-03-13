import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import clsx from 'clsx';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type {
  Site,
  Deployment,
  DomainResponse,
  DNSRecord,
  PipelineRunSummary,
  PipelineStage,
  HealthEvent,
  LinkedService,
  NotificationConfig,
  PreviewEnvironment,
  Membership,
} from '../api/client';
import {
  ArrowLeft,
  Play,
  Square,
  RotateCw,
  Rocket,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  ExternalLink,
  Copy,
  Check,
  GitBranch,
  GitCommit,
  ChevronDown,
  ChevronRight,
  Ban,
  Eye,
  EyeOff,
  RefreshCw,
  Globe,
  Hash,
  Mail,
  Database,
  Zap,
  Bell,
  Layers,
  Settings,
  Shield,
  Container,
  Package,
  AlertCircle,
} from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { useRegistryHost } from '../hooks/useRegistryHost';

// ── Helpers ──────────────────────────────────────────────────

function relativeTime(dateStr?: string | null): string {
  if (!dateStr) return '—';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;
  if (diff < 0) return 'just now';
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—';
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}m ${secs}s`;
}

function durationBetween(start?: string | null, end?: string | null): string {
  if (!start) return '—';
  const s = new Date(start).getTime();
  const e = end ? new Date(end).getTime() : Date.now();
  return formatDuration(e - s);
}

// ── Tab Types ────────────────────────────────────────────────

type TabId =
  | 'overview'
  | 'pipelines'
  | 'git'
  | 'env'
  | 'domains'
  | 'health'
  | 'services'
  | 'notifications'
  | 'previews'
  | 'deployments'
  | 'logs'
  | 'members';

// ── Main Component ───────────────────────────────────────────

export default function SiteDetail() {
  const { siteId } = useParams<{ siteId: string }>();
  const qc = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  const { data: site } = useQuery({
    queryKey: ['site', siteId],
    queryFn: () => api.getSite(siteId!),
    refetchInterval: 10000,
  });
  const { data: workspace } = useQuery({
    queryKey: ['workspace', site?.workspace_id],
    queryFn: () => api.getWorkspace(site!.workspace_id),
    enabled: !!site?.workspace_id,
  });
  const { data: tenant } = useQuery({
    queryKey: ['tenant', site?.tenant_id],
    queryFn: () => api.getTenant(site!.tenant_id),
    enabled: !!site?.tenant_id,
  });
  const { data: containerStatus } = useQuery({
    queryKey: ['site-status', siteId],
    queryFn: () => api.getSiteStatus(siteId!),
    refetchInterval: 5000,
  });

  const liveStatus =
    containerStatus?.status === 'running'
      ? 'running'
      : containerStatus?.status === 'not_found'
        ? 'stopped'
        : containerStatus?.status === 'exited'
          ? 'stopped'
          : site?.status ?? 'stopped';

  const siteUrl = site?.host_port
    ? `http://${site.slug}.${workspace?.slug ?? '...'}.${tenant?.slug ?? '...'}.localhost`
    : null;

  const deployMut = useMutation({
    mutationFn: () => api.deploySite(siteId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['site', siteId] });
      qc.invalidateQueries({ queryKey: ['site-status', siteId] });
      qc.invalidateQueries({ queryKey: ['pipelines', siteId] });
    },
    onError: (err) => {
      console.error('Deploy failed:', err);
      alert(`Deploy failed: ${err.message}`);
    },
  });
  const stopMut = useMutation({
    mutationFn: () => api.stopSite(siteId!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site', siteId] }),
  });
  const restartMut = useMutation({
    mutationFn: () => api.restartSite(siteId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['site', siteId] });
      qc.invalidateQueries({ queryKey: ['site-status', siteId] });
    },
  });

  const tabs: { id: TabId; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'pipelines', label: 'Pipelines' },
    { id: 'git', label: 'Git Config' },
    { id: 'env', label: 'Env Vars' },
    { id: 'domains', label: 'Domains' },
    { id: 'health', label: 'Health' },
    { id: 'services', label: 'Linked Services' },
    { id: 'notifications', label: 'Notifications' },
    { id: 'previews', label: 'Previews' },
    { id: 'deployments', label: 'Deployments' },
    { id: 'logs', label: 'Logs' },
    { id: 'members', label: 'Members' },
  ];

  return (
    <div className="p-6">
      <Link
        to={`/workspaces/${site?.workspace_id}`}
        className="flex items-center gap-1 text-sm text-muted hover:text-gray-700 dark:hover:text-gray-300 mb-4"
      >
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl text-heading">{site?.name ?? '...'}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-faint font-mono">{site?.slug}</span>
            {site && <StatusBadge status={liveStatus} />}
          </div>
        </div>
        <div className="flex gap-2">
          {liveStatus !== 'running' ? (
            /* ── Stopped: Start + Deploy ── */
            <>
              <button
                onClick={() => restartMut.mutate()}
                disabled={restartMut.isPending}
                className="flex items-center gap-1.5 bg-green-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-green-700 active:bg-green-800 disabled:opacity-50"
              >
                <Play className="w-4 h-4" /> {restartMut.isPending ? 'Starting...' : 'Start'}
              </button>
              <button
                onClick={() => deployMut.mutate()}
                disabled={deployMut.isPending}
                className="flex items-center gap-1.5 border border-blue-300 dark:border-blue-600 text-blue-600 dark:text-blue-400 px-3 py-2 rounded-lg text-sm hover:bg-blue-50 dark:hover:bg-blue-900/20 active:bg-blue-100 disabled:opacity-50"
              >
                <Rocket className="w-4 h-4" /> {deployMut.isPending ? 'Building...' : 'Rebuild & Deploy'}
              </button>
            </>
          ) : (
            /* ── Running: Restart + Stop ── */
            <>
              <button
                onClick={() => restartMut.mutate()}
                disabled={restartMut.isPending}
                className="flex items-center gap-1.5 border border-blue-300 dark:border-blue-600 text-blue-600 dark:text-blue-400 px-3 py-2 rounded-lg text-sm hover:bg-blue-50 dark:hover:bg-blue-900/20 active:bg-blue-100 disabled:opacity-50"
              >
                <RotateCw className="w-4 h-4" /> {restartMut.isPending ? 'Restarting...' : 'Restart'}
              </button>
              <button
                onClick={() => stopMut.mutate()}
                disabled={stopMut.isPending}
                className="flex items-center gap-1.5 border border-red-300 dark:border-red-600 text-red-600 dark:text-red-400 px-3 py-2 rounded-lg text-sm hover:bg-red-50 dark:hover:bg-red-900/20 active:bg-red-100 disabled:opacity-50"
              >
                <Square className="w-4 h-4" /> {stopMut.isPending ? 'Stopping...' : 'Stop'}
              </button>
            </>
          )}
        </div>
      </div>

      {siteUrl && liveStatus === 'running' && <SiteUrlBar url={siteUrl} />}

      {/* Tabs */}
      <div className="tab-bar overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={clsx('tab', activeTab === t.id && 'active')}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && <OverviewTab site={site} containerStatus={containerStatus} />}
      {activeTab === 'pipelines' && <PipelinesTab siteId={siteId!} site={site} />}
      {activeTab === 'git' && <GitConfigTab siteId={siteId!} site={site} />}
      {activeTab === 'env' && <EnvTab siteId={siteId!} />}
      {activeTab === 'domains' && <DomainsTab siteId={siteId!} site={site} />}
      {activeTab === 'health' && <HealthTab siteId={siteId!} />}
      {activeTab === 'services' && <LinkedServicesTab siteId={siteId!} />}
      {activeTab === 'notifications' && <NotificationsTab siteId={siteId!} />}
      {activeTab === 'previews' && <PreviewsTab siteId={siteId!} />}
      {activeTab === 'deployments' && <DeploymentsTab siteId={siteId!} />}
      {activeTab === 'logs' && <LogsTab siteId={siteId!} site={site} />}
      {activeTab === 'members' && <MembersTab siteId={siteId!} />}
    </div>
  );
}

// ── Shared Sub-components ────────────────────────────────────

function Row({ label, value }: { label: string; value: any }) {
  return (
    <div className="flex justify-between">
      <dt className="text-muted">{label}</dt>
      <dd className="font-mono text-heading">{String(value)}</dd>
    </div>
  );
}

function SiteUrlBar({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="flex items-center gap-2 mb-6 bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-700 rounded-lg px-4 py-2.5">
      <span className="text-xs section-label">URL</span>
      <code className="flex-1 text-sm font-mono text-label truncate">{url}</code>
      <button
        onClick={handleCopy}
        className="flex items-center gap-1 text-xs text-muted hover:text-gray-700 dark:hover:text-gray-300 border dark:border-gray-600 rounded px-2.5 py-1.5 hover:bg-white dark:hover:bg-gray-700 active:bg-gray-200 transition-colors"
        title="Copy URL"
      >
        {copied ? (
          <Check className="w-3.5 h-3.5 text-green-500" />
        ) : (
          <Copy className="w-3.5 h-3.5" />
        )}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1 text-xs text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 rounded px-2.5 py-1.5 transition-colors"
      >
        <ExternalLink className="w-3.5 h-3.5" /> Open
      </a>
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={handleCopy}
      className="text-faint hover:text-gray-600 dark:hover:text-gray-300"
      title="Copy to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

// ── Overview Tab ─────────────────────────────────────────────

function OverviewTab({ site, containerStatus }: { site: any; containerStatus: any }) {
  const registryHost = useRegistryHost();
  if (!site) return null;

  const cStatus = containerStatus?.status ?? 'unknown';
  const isRunning = cStatus === 'running';
  const isDown = cStatus === 'not_found' || cStatus === 'exited' || cStatus === 'dead';

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div className="card p-5">
          <h3 className="text-heading mb-3">Site Config</h3>
          <dl className="text-sm space-y-2">
            <Row label="Source Type" value={site.source_type} />
            <Row label="Source URL" value={site.source_url || '\u2014'} />
            <Row label="Container Port" value={site.container_port} />
            <Row label="Host Port" value={site.host_port ?? 'Auto-assign on deploy'} />
            <Row label="Deploy Target" value={site.deploy_target} />
            <Row label="Health Check" value={site.health_check_path} />
          </dl>
        </div>
        <div className={`card p-5 ${isDown ? 'border-gray-300 dark:border-gray-600' : ''}`}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-heading">Container Status</h3>
            <div className="flex items-center gap-2">
              <span
                className={`inline-block w-2.5 h-2.5 rounded-full ${
                  isRunning ? 'bg-green-500 animate-pulse' : isDown ? 'bg-gray-400' : 'bg-yellow-500'
                }`}
              />
              <span
                className={`text-sm font-medium ${
                  isRunning ? 'text-green-700' : isDown ? 'text-gray-500' : 'text-yellow-700'
                }`}
              >
                {isRunning ? 'Running' : isDown ? 'Not Running' : cStatus}
              </span>
            </div>
          </div>
          {isDown ? (
            <p className="text-sm text-muted">
              Container is not running. Click <strong>Start</strong> to launch it.
            </p>
          ) : (
            <dl className="text-sm space-y-2">
              <Row label="Container ID" value={containerStatus?.container_id ?? '\u2014'} />
              <Row label="Image" value={containerStatus?.image ?? '\u2014'} />
              <Row label="Name" value={containerStatus?.name ?? '\u2014'} />
            </dl>
          )}
        </div>
      </div>

      {/* Deploy Updates — contextual instructions per source type */}
      <div className="card p-5">
        <h3 className="text-heading mb-3 flex items-center gap-2">
          <Rocket className="w-4 h-4 text-blue-400" />
          Deploy Updates
        </h3>

        {site.source_type === 'git_repo' && (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              {site.auto_deploy
                ? <>Push to <code className="font-mono bg-black/20 px-1.5 py-0.5 rounded text-xs">{site.git_branch || 'main'}</code> and this site auto-deploys via webhook.</>
                : <>Push to your repo and click <strong>Rebuild &amp; Deploy</strong> above, or enable auto-deploy in the Git tab.</>}
            </p>
            {site.auto_deploy && site.git_provider && (
              <div className="text-xs text-muted p-3 rounded-lg bg-black/10 border border-white/5">
                <p className="font-medium text-heading mb-1">Webhook URL</p>
                <code className="text-emerald-400">{`${window.location.origin}/api/v1/webhooks/${site.git_provider}`}</code>
              </div>
            )}
            {!site.git_token && (
              <p className="text-xs text-amber-400">
                <AlertCircle className="w-3 h-3 inline mr-1" />
                No deploy token configured. Private repos will fail to clone. Add one in the Git tab.
              </p>
            )}
          </div>
        )}

        {site.source_type === 'docker_image' && (
          <div className="space-y-3">
            <p className="text-sm text-muted">Build and push a new image, then click <strong>Rebuild &amp; Deploy</strong> above.</p>
            <pre className="bg-gray-900 text-green-400 font-mono text-xs rounded p-3 overflow-x-auto whitespace-pre">{`# Build and push your updated image
docker build -t ${registryHost}/${site.slug}:latest .
docker push ${registryHost}/${site.slug}:latest

# Then click "Rebuild & Deploy" in the UI, or:
adhara-engine site deploy <tenant>/<workspace>/${site.slug}`}</pre>
          </div>
        )}

        {site.source_type === 'docker_registry' && (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              Push a new image tag to the registry, then click <strong>Rebuild &amp; Deploy</strong> above.
            </p>
            {site.source_url && (
              <pre className="bg-gray-900 text-green-400 font-mono text-xs rounded p-3 overflow-x-auto whitespace-pre">{`# Current image: ${site.source_url}
# Push an updated tag, then redeploy:
adhara-engine site deploy <tenant>/<workspace>/${site.slug}`}</pre>
            )}
          </div>
        )}

        {site.source_type === 'upload' && (
          <p className="text-sm text-muted">Upload updated source files and click <strong>Rebuild &amp; Deploy</strong> above.</p>
        )}
      </div>
    </div>
  );
}

// ── Pipeline Config Card ─────────────────────────────────────

// ── Pipeline Stage Definitions ───────────────────────────────

interface StageConfig {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  activeColor: string;
  description: string;
  appliesTo: string[]; // source_types where this stage is relevant
}

const STAGE_DEFS: StageConfig[] = [
  {
    id: 'source',
    label: 'Source',
    icon: GitBranch,
    color: 'bg-slate-50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-700',
    activeColor: 'bg-slate-100 dark:bg-slate-800 border-slate-400 dark:border-slate-500 ring-2 ring-slate-200 dark:ring-slate-700',
    description: 'Where the code comes from',
    appliesTo: ['git_repo', 'docker_image', 'docker_registry', 'upload'],
  },
  {
    id: 'scan',
    label: 'Scan',
    icon: Shield,
    color: 'bg-amber-50 dark:bg-amber-900/20 border-amber-200 dark:border-amber-800',
    activeColor: 'bg-amber-100 dark:bg-amber-900/40 border-amber-400 dark:border-amber-600 ring-2 ring-amber-200 dark:ring-amber-800',
    description: 'Security vulnerability scanning',
    appliesTo: ['git_repo'],
  },
  {
    id: 'build',
    label: 'Build',
    icon: Container,
    color: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800',
    activeColor: 'bg-blue-100 dark:bg-blue-900/40 border-blue-400 dark:border-blue-600 ring-2 ring-blue-200 dark:ring-blue-800',
    description: 'Build a Docker image from source',
    appliesTo: ['git_repo', 'upload'],
  },
  {
    id: 'registry',
    label: 'Registry',
    icon: Package,
    color: 'bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800',
    activeColor: 'bg-purple-100 dark:bg-purple-900/40 border-purple-400 dark:border-purple-600 ring-2 ring-purple-200 dark:ring-purple-800',
    description: 'Push image to the container registry',
    appliesTo: ['git_repo', 'upload'],
  },
  {
    id: 'deploy',
    label: 'Deploy',
    icon: Rocket,
    color: 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800',
    activeColor: 'bg-green-100 dark:bg-green-900/40 border-green-400 dark:border-green-600 ring-2 ring-green-200 dark:ring-green-800',
    description: 'Deploy the container to a target',
    appliesTo: ['git_repo', 'docker_image', 'docker_registry', 'upload'],
  },
];

function Toggle({ enabled, onToggle }: { enabled: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
        enabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

// ── Stage Summary Helpers ────────────────────────────────────

function stageStatus(stageId: string, site?: Site, registryHost?: string): { label: string; ok: boolean } {
  if (!site) return { label: '...', ok: false };
  switch (stageId) {
    case 'source':
      if (site.source_type === 'git_repo') {
        return site.source_url
          ? { label: site.source_url.replace(/https?:\/\//, '').slice(0, 40), ok: true }
          : { label: 'Not configured', ok: false };
      }
      if (site.source_type === 'docker_image' || site.source_type === 'docker_registry') {
        return site.source_url
          ? { label: site.source_url, ok: true }
          : { label: 'No image URL', ok: false };
      }
      return { label: site.source_type, ok: true };
    case 'scan':
      return site.scan_enabled
        ? { label: `Semgrep (${site.scan_fail_on ?? 'critical'})`, ok: true }
        : { label: 'Disabled', ok: true };
    case 'build':
      return { label: (site.build_driver ?? 'local_docker').replace(/_/g, ' '), ok: true };
    case 'registry':
      return { label: registryHost || 'registry', ok: true };
    case 'deploy': {
      const target = site.deploy_target ?? 'local';
      const labels: Record<string, string> = {
        local: 'Local Docker',
        cloud_run: 'Google Cloud Run',
        aws_ecs: 'AWS ECS',
        azure_container: 'Azure Container',
        kubernetes: 'Kubernetes',
      };
      return { label: labels[target] ?? target, ok: true };
    }
    default:
      return { label: '—', ok: false };
  }
}

// ── Stage Config Panels ──────────────────────────────────────

function SourceConfigPanel({ siteId, site }: { siteId: string; site?: Site }) {
  if (!site) return null;
  const isGit = site.source_type === 'git_repo';
  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs text-label mb-1">Source Type</p>
        <p className="text-sm text-heading font-mono">{site.source_type}</p>
      </div>
      <div>
        <p className="text-xs text-label mb-1">Source URL</p>
        <p className="text-sm text-heading font-mono break-all">{site.source_url ?? 'Not set'}</p>
      </div>
      {isGit && (
        <div className="flex gap-4">
          <div>
            <p className="text-xs text-label mb-1">Branch</p>
            <p className="text-sm text-heading font-mono">{site.git_branch ?? 'main'}</p>
          </div>
          <div>
            <p className="text-xs text-label mb-1">Auto-Deploy</p>
            <p className="text-sm text-heading">{site.auto_deploy ? 'Yes' : 'No'}</p>
          </div>
        </div>
      )}
      {isGit && (
        <Link to={`/sites/${siteId}`} onClick={() => {}} className="text-xs link inline-flex items-center gap-1">
          <Settings className="w-3 h-3" /> Edit in Git Config tab
        </Link>
      )}
    </div>
  );
}

function ScanConfigPanel({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const [enabled, setEnabled] = useState(site?.scan_enabled ?? false);
  const [failOn, setFailOn] = useState(site?.scan_fail_on ?? 'critical');

  useEffect(() => {
    if (site) {
      setEnabled(site.scan_enabled ?? false);
      setFailOn(site.scan_fail_on ?? 'critical');
    }
  }, [site]);

  const saveMut = useMutation({
    mutationFn: () => api.updateSite(siteId, { scan_enabled: enabled, scan_fail_on: failOn } as Partial<Site>),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site', siteId] }),
  });

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-label">Security Scan</p>
          <p className="text-xs text-muted">Run Semgrep vulnerability scan</p>
        </div>
        <Toggle enabled={enabled} onToggle={() => setEnabled(!enabled)} />
      </div>
      {enabled && (
        <div>
          <label className="block text-xs text-label mb-1">Fail Threshold</label>
          <select
            value={failOn}
            onChange={(e) => setFailOn(e.target.value)}
            className="border dark:border-gray-600 rounded px-3 py-1.5 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
          >
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      )}
      <button
        onClick={() => saveMut.mutate()}
        disabled={saveMut.isPending}
        className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {saveMut.isPending ? 'Saving...' : 'Save'}
      </button>
      {saveMut.isSuccess && <span className="text-xs text-green-600 dark:text-green-400 ml-2">Saved</span>}
    </div>
  );
}

function BuildConfigPanel({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const [driver, setDriver] = useState(site?.build_driver ?? 'local_docker');

  useEffect(() => {
    if (site) setDriver(site.build_driver ?? 'local_docker');
  }, [site]);

  const saveMut = useMutation({
    mutationFn: () => api.updateSite(siteId, { build_driver: driver } as Partial<Site>),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site', siteId] }),
  });

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-label mb-1">Build Driver</label>
        <select
          value={driver}
          onChange={(e) => setDriver(e.target.value)}
          className="border dark:border-gray-600 rounded px-3 py-1.5 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
        >
          <option value="local_docker">Local Docker</option>
          <option value="local_buildkit">Local BuildKit</option>
          <option value="gcp_cloud_build">GCP Cloud Build</option>
          <option value="aws_codebuild">AWS CodeBuild</option>
        </select>
      </div>
      <div>
        <p className="text-xs text-label mb-1">Dockerfile</p>
        <p className="text-sm text-heading font-mono">{site?.dockerfile_path ?? 'Dockerfile'}</p>
      </div>
      <button
        onClick={() => saveMut.mutate()}
        disabled={saveMut.isPending}
        className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {saveMut.isPending ? 'Saving...' : 'Save'}
      </button>
      {saveMut.isSuccess && <span className="text-xs text-green-600 dark:text-green-400 ml-2">Saved</span>}
    </div>
  );
}

function RegistryConfigPanel({ siteId }: { siteId: string }) {
  const registryHost = useRegistryHost();
  const { data, isLoading } = useQuery({
    queryKey: ['site-images', siteId],
    queryFn: () => api.listSiteImages(siteId),
  });

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs text-label mb-1">Registry</p>
        <p className="text-sm text-heading font-mono">{registryHost}</p>
      </div>
      <div>
        <p className="text-xs text-label mb-1">Repository</p>
        <p className="text-sm text-heading font-mono">{data?.repository ?? '...'}</p>
      </div>
      <div>
        <p className="text-xs text-label mb-1">Tags</p>
        {isLoading && <p className="text-xs text-muted">Loading...</p>}
        {data?.tags && data.tags.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {data.tags.slice(0, 10).map((tag) => (
              <span key={tag} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-mono bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600">
                {tag}
              </span>
            ))}
            {data.tags.length > 10 && <span className="text-xs text-muted">+{data.tags.length - 10} more</span>}
          </div>
        ) : (
          <p className="text-xs text-muted">No images yet</p>
        )}
      </div>
      <Link to="/registry" className="text-xs link inline-flex items-center gap-1">
        <ExternalLink className="w-3 h-3" /> View full registry
      </Link>
    </div>
  );
}

function DeployConfigPanel({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const [target, setTarget] = useState(site?.deploy_target ?? 'local');
  const [healthAuto, setHealthAuto] = useState(site?.health_auto_remediate ?? false);

  useEffect(() => {
    if (site) {
      setTarget(site.deploy_target ?? 'local');
      setHealthAuto(site.health_auto_remediate ?? false);
    }
  }, [site]);

  const saveMut = useMutation({
    mutationFn: () => api.updateSite(siteId, { deploy_target: target, health_auto_remediate: healthAuto } as Partial<Site>),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site', siteId] }),
  });

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-label mb-1">Deploy Target</label>
        <select
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          className="border dark:border-gray-600 rounded px-3 py-1.5 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
        >
          <option value="local">Local Docker</option>
          <option value="cloud_run">Google Cloud Run</option>
          <option value="aws_ecs">AWS ECS</option>
          <option value="azure_container">Azure Container Apps</option>
          <option value="kubernetes">Kubernetes</option>
        </select>
      </div>
      <div>
        <p className="text-xs text-label mb-1">Health Check</p>
        <p className="text-sm text-heading font-mono">{site?.health_check_path ?? '/api/health'}</p>
      </div>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-label">Auto-Remediation</p>
          <p className="text-xs text-muted">Restart on health failure</p>
        </div>
        <Toggle enabled={healthAuto} onToggle={() => setHealthAuto(!healthAuto)} />
      </div>
      <button
        onClick={() => saveMut.mutate()}
        disabled={saveMut.isPending}
        className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {saveMut.isPending ? 'Saving...' : 'Save'}
      </button>
      {saveMut.isSuccess && <span className="text-xs text-green-600 dark:text-green-400 ml-2">Saved</span>}
    </div>
  );
}

// ── Smart Pipeline Flow ──────────────────────────────────────

function PipelineFlow({ siteId, site }: { siteId: string; site?: Site }) {
  const [activeStage, setActiveStage] = useState<string | null>(null);
  const registryHost = useRegistryHost();

  const sourceType = site?.source_type ?? 'git_repo';
  const relevantStages = STAGE_DEFS.filter((s) => s.appliesTo.includes(sourceType));

  // For scan: also check if it's disabled to dim it
  const isScanDisabled = !site?.scan_enabled && sourceType === 'git_repo';

  const renderPanel = () => {
    switch (activeStage) {
      case 'source': return <SourceConfigPanel siteId={siteId} site={site} />;
      case 'scan': return <ScanConfigPanel siteId={siteId} site={site} />;
      case 'build': return <BuildConfigPanel siteId={siteId} site={site} />;
      case 'registry': return <RegistryConfigPanel siteId={siteId} />;
      case 'deploy': return <DeployConfigPanel siteId={siteId} site={site} />;
      default: return null;
    }
  };

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-heading">Pipeline</h3>
        <span className="text-xs text-muted px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700">
          {sourceType.replace(/_/g, ' ')}
        </span>
      </div>

      {/* Interactive flow diagram */}
      <div className="flex items-stretch gap-0 overflow-x-auto pb-2">
        {relevantStages.map((stage, i) => {
          const active = activeStage === stage.id;
          const status = stageStatus(stage.id, site, registryHost);
          const dimmed = stage.id === 'scan' && isScanDisabled;
          const Icon = stage.icon;

          return (
            <div key={stage.id} className="flex items-stretch flex-shrink-0">
              <button
                onClick={() => setActiveStage(active ? null : stage.id)}
                className={clsx(
                  'relative flex flex-col items-center gap-1.5 px-4 py-3 rounded-lg border transition-all min-w-[100px]',
                  active ? stage.activeColor : stage.color,
                  dimmed && 'opacity-40',
                  'hover:shadow-md cursor-pointer',
                )}
              >
                <Icon className="w-5 h-5" />
                <span className="text-xs font-semibold">{stage.label}</span>
                <span className={clsx('text-[10px] leading-tight text-center max-w-[90px] truncate', status.ok ? 'text-muted' : 'text-red-500 font-medium')}>
                  {dimmed ? 'Disabled' : status.label}
                </span>
                {status.ok ? (
                  <CheckCircle className="w-3 h-3 text-green-500 absolute top-1.5 right-1.5" />
                ) : (
                  <XCircle className="w-3 h-3 text-red-400 absolute top-1.5 right-1.5" />
                )}
              </button>
              {i < relevantStages.length - 1 && (
                <div className="flex items-center px-1">
                  <ChevronRight className="w-4 h-4 text-gray-300 dark:text-gray-600" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Active stage config panel */}
      {activeStage && (
        <div className="mt-4 border-t dark:border-gray-700 pt-4">
          <div className="flex items-center gap-2 mb-3">
            <Settings className="w-4 h-4 text-muted" />
            <span className="text-sm text-label font-medium">
              {STAGE_DEFS.find(s => s.id === activeStage)?.label} Configuration
            </span>
          </div>
          {renderPanel()}
        </div>
      )}
    </div>
  );
}

// ── Pipelines Tab ────────────────────────────────────────────

function PipelinesTab({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const { data: pipelines } = useQuery({
    queryKey: ['pipelines', siteId],
    queryFn: () => api.listPipelines(siteId),
    refetchInterval: 5000,
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showFinished, setShowFinished] = useState(false);

  const pendingCount = pipelines?.filter(p => p.status === 'pending').length ?? 0;
  const activeRuns = pipelines?.filter(p => p.status === 'running' || p.status === 'pending') ?? [];
  const finishedRuns = pipelines?.filter(p => p.status !== 'running' && p.status !== 'pending') ?? [];
  const finishedCount = finishedRuns.length;

  // Show active runs always, finished only when toggled
  const visibleRuns = showFinished ? [...activeRuns, ...finishedRuns] : activeRuns;
  // If no active runs, always show finished
  const displayRuns = activeRuns.length === 0 ? (pipelines ?? []) : visibleRuns;

  const cancelAllMut = useMutation({
    mutationFn: () => api.cancelPendingPipelines(siteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pipelines', siteId] }),
  });

  const clearHistoryMut = useMutation({
    mutationFn: () => api.clearPipelineHistory(siteId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['pipelines', siteId] }),
  });

  const isDockerImage = site?.source_type === 'docker_image' || site?.source_type === 'docker_registry';

  return (
    <div className="space-y-4">
      {/* Smart interactive pipeline flow */}
      <PipelineFlow siteId={siteId} site={site} />

      {/* Info banner for docker_image sites */}
      {isDockerImage && pipelines && pipelines.length > 0 && pipelines.some(p => p.trigger === 'health_rebuild') && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/50 rounded-lg px-4 py-3">
          <p className="text-xs text-amber-800 dark:text-amber-300">
            <strong>Note:</strong> This site uses a pre-built Docker image, so "Health Rebuild" pipeline runs cannot rebuild from source.
            The health monitor now restarts the container instead. You can safely clear the old runs below.
          </p>
        </div>
      )}

      {/* Pipeline runs */}
      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b dark:border-gray-700">
          <h3 className="text-heading text-sm">Pipeline Runs</h3>
          <div className="flex items-center gap-3">
            {finishedCount > 0 && (
              <button
                onClick={() => clearHistoryMut.mutate()}
                disabled={clearHistoryMut.isPending}
                className="flex items-center gap-1.5 text-xs text-muted hover:text-body disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                {clearHistoryMut.isPending ? 'Clearing...' : `Clear ${finishedCount} finished`}
              </button>
            )}
            {pendingCount > 0 && (
              <button
                onClick={() => cancelAllMut.mutate()}
                disabled={cancelAllMut.isPending}
                className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5" />
                {cancelAllMut.isPending ? 'Cancelling...' : `Cancel ${pendingCount} pending`}
              </button>
            )}
          </div>
        </div>

        {/* Show/hide finished toggle when there are active runs */}
        {activeRuns.length > 0 && finishedCount > 0 && (
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800/30 border-b dark:border-gray-700">
            <button
              onClick={() => setShowFinished(!showFinished)}
              className="text-xs text-muted hover:text-body"
            >
              {showFinished ? 'Hide' : 'Show'} {finishedCount} finished run{finishedCount !== 1 ? 's' : ''}
            </button>
          </div>
        )}

        <table className="w-full text-sm">
          <thead className="thead">
            <tr>
              <th className="px-4 py-3 w-8"></th>
              <th className="px-4 py-3 font-medium">Trigger</th>
              <th className="px-4 py-3 font-medium">Commit</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Started</th>
              <th className="px-4 py-3 font-medium">Duration</th>
              <th className="px-4 py-3 w-32"></th>
            </tr>
          </thead>
          <tbody className="tbody">
            {displayRuns.map((p: PipelineRunSummary) => (
              <PipelineRow
                key={p.id}
                pipeline={p}
                siteId={siteId}
                expanded={expandedId === p.id}
                onToggle={() => setExpandedId(expandedId === p.id ? null : p.id)}
              />
            ))}
            {(!pipelines || pipelines.length === 0) && (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-faint">
                  {isDockerImage
                    ? 'No pipeline runs. This site deploys directly from a Docker image.'
                    : <>No pipeline runs yet. Click <strong>Rebuild &amp; Deploy</strong> to start one.</>
                  }
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TriggerIcon({ trigger }: { trigger: string }) {
  switch (trigger) {
    case 'git_push':
    case 'webhook':
      return <GitBranch className="w-4 h-4 text-purple-500" />;
    case 'manual':
      return <Play className="w-4 h-4 text-blue-500" />;
    case 'retry':
      return <RefreshCw className="w-4 h-4 text-orange-500" />;
    case 'health_rebuild':
      return <RotateCw className="w-4 h-4 text-amber-500" />;
    case 'polling':
      return <RefreshCw className="w-4 h-4 text-teal-500" />;
    default:
      return <Rocket className="w-4 h-4 text-gray-400" />;
  }
}

function PipelineRow({
  pipeline,
  siteId,
  expanded,
  onToggle,
}: {
  pipeline: PipelineRunSummary;
  siteId: string;
  expanded: boolean;
  onToggle: () => void;
}) {
  const qc = useQueryClient();
  const { data: detail } = useQuery({
    queryKey: ['pipeline', pipeline.id],
    queryFn: () => api.getPipeline(pipeline.id),
    enabled: expanded,
    refetchInterval: expanded && (pipeline.status === 'running' || pipeline.status === 'pending') ? 3000 : false,
  });
  const cancelMut = useMutation({
    mutationFn: () => api.cancelPipeline(pipeline.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipelines', siteId] });
      qc.invalidateQueries({ queryKey: ['pipeline', pipeline.id] });
    },
  });

  const retryMut = useMutation({
    mutationFn: () => api.retryPipeline(pipeline.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['pipelines', siteId] });
    },
  });

  const isRunning = pipeline.status === 'running' || pipeline.status === 'pending';
  const isRetryable = pipeline.status === 'failed' || pipeline.status === 'cancelled';

  return (
    <>
      <tr
        className="trow cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-4 py-3">
          {expanded ? (
            <ChevronDown className="w-4 h-4 text-faint" />
          ) : (
            <ChevronRight className="w-4 h-4 text-faint" />
          )}
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <TriggerIcon trigger={pipeline.trigger} />
            <span className="capitalize">{pipeline.trigger.replace('_', ' ')}</span>
          </div>
        </td>
        <td className="px-4 py-3 font-mono text-xs">
          {pipeline.commit_sha ? pipeline.commit_sha.slice(0, 8) : '\u2014'}
        </td>
        <td className="px-4 py-3">
          <StatusBadge status={pipeline.status} />
        </td>
        <td className="px-4 py-3 text-muted text-xs">
          {relativeTime(pipeline.started_at || pipeline.created_at)}
        </td>
        <td className="px-4 py-3 text-muted text-xs">
          {durationBetween(pipeline.started_at, pipeline.finished_at)}
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {isRunning && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  cancelMut.mutate();
                }}
                disabled={cancelMut.isPending}
                className="flex items-center gap-1 text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
              >
                <Ban className="w-3.5 h-3.5" /> Cancel
              </button>
            )}
            {isRetryable && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  retryMut.mutate();
                }}
                disabled={retryMut.isPending}
                className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 disabled:opacity-50"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry
              </button>
            )}
          </div>
        </td>
      </tr>
      {expanded && detail && (
        <tr>
          <td colSpan={7} className="px-4 py-4 bg-gray-50 dark:bg-gray-800/50">
            <PipelineStages stages={detail.stages} />
            {detail.commit_message && (
              <p className="mt-3 text-xs text-muted">
                <GitCommit className="w-3.5 h-3.5 inline mr-1" />
                {detail.commit_message}
                {detail.commit_author && (
                  <span className="ml-2 text-faint">by {detail.commit_author}</span>
                )}
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

function PipelineStages({ stages }: { stages: PipelineStage[] }) {
  const [openLog, setOpenLog] = useState<string | null>(null);
  const sorted = [...stages].sort((a, b) => a.order - b.order);

  const stageColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'running':
        return 'bg-blue-500 animate-pulse';
      case 'skipped':
        return 'bg-gray-300';
      case 'pending':
      default:
        return 'bg-gray-400';
    }
  };

  const stageTextColor = (status: string) => {
    switch (status) {
      case 'passed':
        return 'text-green-700';
      case 'failed':
        return 'text-red-700';
      case 'running':
        return 'text-blue-700';
      case 'skipped':
        return 'text-gray-400';
      case 'pending':
      default:
        return 'text-gray-500';
    }
  };

  return (
    <div>
      {/* Progress bar */}
      <div className="flex items-center gap-1 mb-3">
        {sorted.map((stage, i) => (
          <div key={stage.id} className="flex items-center gap-1 flex-1">
            <div className={`h-2 flex-1 rounded-full ${stageColor(stage.status)}`} />
            {i < sorted.length - 1 && <ChevronRight className="w-3 h-3 text-gray-300 flex-shrink-0" />}
          </div>
        ))}
      </div>
      {/* Stage details */}
      <div className="space-y-2">
        {sorted.map((stage) => (
          <div key={stage.id} className="bg-white dark:bg-gray-800 rounded border dark:border-gray-700 p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${stageColor(stage.status)}`} />
                <span className={`text-sm font-medium ${stageTextColor(stage.status)}`}>
                  {stage.name}
                </span>
                <span className="text-xs text-faint capitalize">{stage.status}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-faint">
                  {formatDuration(stage.duration_ms)}
                </span>
                {stage.logs && (
                  <button
                    onClick={() => setOpenLog(openLog === stage.id ? null : stage.id)}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                  >
                    {openLog === stage.id ? 'Hide Logs' : 'View Logs'}
                  </button>
                )}
              </div>
            </div>
            {stage.error && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1">
                {stage.error}
              </p>
            )}
            {openLog === stage.id && stage.logs && (
              <div className="mt-2 bg-gray-900 text-green-400 rounded p-3 font-mono text-xs overflow-auto max-h-64">
                {stage.logs.split('\n').map((line, i) => (
                  <div key={i} className="leading-5">
                    {line}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Git Config Tab ───────────────────────────────────────────

function GitConfigTab({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const [gitProvider, setGitProvider] = useState(site?.git_provider || 'github');
  const [sourceUrl, setSourceUrl] = useState(site?.source_url || '');
  const [gitBranch, setGitBranch] = useState(site?.git_branch || 'main');
  const [autoDeploy, setAutoDeploy] = useState(site?.auto_deploy ?? false);
  const [webhookSecret, setWebhookSecret] = useState(site?.webhook_secret || '');
  const [gitTokenUsername, setGitTokenUsername] = useState(site?.git_token_username || '');
  const [gitToken, setGitToken] = useState(site?.git_token || '');
  const [showToken, setShowToken] = useState(false);

  useEffect(() => {
    if (site) {
      setGitProvider(site.git_provider || 'github');
      setSourceUrl(site.source_url || '');
      setGitBranch(site.git_branch || 'main');
      setAutoDeploy(site.auto_deploy ?? false);
      setWebhookSecret(site.webhook_secret || '');
      setGitTokenUsername(site.git_token_username || '');
      setGitToken(site.git_token || '');
    }
  }, [site]);

  const saveMut = useMutation({
    mutationFn: () =>
      api.updateSite(siteId, {
        git_provider: gitProvider,
        source_url: sourceUrl,
        git_branch: gitBranch,
        auto_deploy: autoDeploy,
        webhook_secret: webhookSecret,
        git_token_username: gitTokenUsername,
        git_token: gitToken,
      } as Partial<Site>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['site', siteId] });
    },
  });

  const webhookUrl =
    gitProvider === 'gitlab' ? '/api/v1/webhooks/gitlab' : '/api/v1/webhooks/github';

  const regenerateSecret = () => {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < 40; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setWebhookSecret(result);
  };

  return (
    <div className="max-w-2xl">
      <div className="card p-5 space-y-4">
        <h3 className="text-heading">Git Integration</h3>

        {/* Git Provider */}
        <div>
          <label className="block text-sm text-label mb-1">Git Provider</label>
          <select
            value={gitProvider}
            onChange={(e) => setGitProvider(e.target.value)}
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
          >
            <option value="github">GitHub</option>
            <option value="gitlab">GitLab</option>
          </select>
        </div>

        {/* Source URL */}
        <div>
          <label className="block text-sm text-label mb-1">Source URL</label>
          <input
            type="text"
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://github.com/org/repo.git"
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        {/* Git Branch */}
        <div>
          <label className="block text-sm text-label mb-1">Branch</label>
          <input
            type="text"
            value={gitBranch}
            onChange={(e) => setGitBranch(e.target.value)}
            placeholder="main"
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        {/* Auto Deploy */}
        <div className="flex items-center justify-between">
          <div>
            <label className="text-sm text-label">Auto Deploy</label>
            <p className="text-xs text-muted">Automatically deploy on push to branch</p>
          </div>
          <button
            type="button"
            onClick={() => setAutoDeploy(!autoDeploy)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              autoDeploy ? 'bg-blue-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                autoDeploy ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>

        {/* Webhook Secret */}
        <div>
          <label className="block text-sm text-label mb-1">Webhook Secret</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={webhookSecret}
              onChange={(e) => setWebhookSecret(e.target.value)}
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 font-mono dark:bg-gray-800 dark:text-gray-200"
            />
            <CopyButton text={webhookSecret} />
            <button
              onClick={regenerateSecret}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 border dark:border-gray-600 rounded px-3 py-2"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Webhook URL */}
        <div>
          <label className="block text-sm text-label mb-1">Webhook URL</label>
          <div className="flex items-center gap-2 bg-gray-50 dark:bg-gray-800/50 border dark:border-gray-600 rounded px-3 py-2">
            <code className="text-sm font-mono text-body flex-1">{webhookUrl}</code>
            <CopyButton text={webhookUrl} />
          </div>
        </div>

        {/* Git Token Username */}
        <div>
          <label className="block text-sm text-label mb-1">
            Git Token Username
          </label>
          <input
            type="text"
            value={gitTokenUsername}
            onChange={(e) => setGitTokenUsername(e.target.value)}
            placeholder="git-username or oauth2"
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
          />
        </div>

        {/* Git Token */}
        <div>
          <label className="block text-sm text-label mb-1">Git Token</label>
          <div className="flex gap-2">
            <input
              type={showToken ? 'text' : 'password'}
              value={gitToken}
              onChange={(e) => setGitToken(e.target.value)}
              placeholder="ghp_xxxxxxxxxxxx"
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 font-mono dark:bg-gray-800 dark:text-gray-200"
            />
            <button
              onClick={() => setShowToken(!showToken)}
              className="text-faint hover:text-gray-600 dark:hover:text-gray-300 border dark:border-gray-600 rounded px-3 py-2"
            >
              {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Save */}
        <div className="flex justify-end pt-2">
          <button
            onClick={() => saveMut.mutate()}
            disabled={saveMut.isPending}
            className="bg-blue-600 text-white px-6 py-2 rounded text-sm hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50"
          >
            {saveMut.isPending ? 'Saving...' : 'Save Git Config'}
          </button>
        </div>
        {saveMut.isSuccess && (
          <p className="text-sm text-green-600">Git configuration saved successfully.</p>
        )}
        {saveMut.isError && (
          <p className="text-sm text-red-600">
            Error: {(saveMut.error as Error).message}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Env Tab ──────────────────────────────────────────────────

function EnvTab({ siteId }: { siteId: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['env', siteId],
    queryFn: () => api.getEnv(siteId),
  });
  const [key, setKey] = useState('');
  const [value, setValue] = useState('');
  const [scope, setScope] = useState('runtime');

  const setMut = useMutation({
    mutationFn: () => api.setEnv(siteId, [{ key, value, scope }]),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['env', siteId] });
      setKey('');
      setValue('');
      if (res.warning) alert(res.warning);
    },
  });
  const delMut = useMutation({
    mutationFn: (k: string) => api.deleteEnv(siteId, k),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['env', siteId] }),
  });

  const envRows = [
    ...Object.entries(data?.runtime_env ?? {}).map(([k, v]) => ({
      key: k,
      value: v,
      scope: 'runtime',
    })),
    ...Object.entries(data?.build_env ?? {}).map(([k, v]) => ({
      key: k,
      value: v,
      scope: 'build',
    })),
  ];

  return (
    <div>
      <div className="card p-5 mb-4">
        <h3 className="text-heading mb-3">Add Variable</h3>
        <div className="flex gap-2">
          <input
            value={key}
            onChange={(e) => setKey(e.target.value)}
            placeholder="KEY"
            className="border rounded px-3 py-2 text-sm font-mono flex-1"
          />
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="value"
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 dark:bg-gray-800 dark:text-gray-200"
          />
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="border dark:border-gray-600 rounded px-3 py-2 text-sm dark:bg-gray-800 dark:text-gray-200"
          >
            <option value="runtime">Runtime</option>
            <option value="build">Build</option>
          </select>
          <button
            onClick={() => setMut.mutate()}
            disabled={!key || !value}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="thead">
            <tr>
              <th className="px-4 py-3 font-medium">Key</th>
              <th className="px-4 py-3 font-medium">Value</th>
              <th className="px-4 py-3 font-medium">Scope</th>
              <th className="px-4 py-3 w-12"></th>
            </tr>
          </thead>
          <tbody className="tbody">
            {envRows.map((r) => (
              <tr key={r.key}>
                <td className="px-4 py-3 font-mono dark:text-gray-200">{r.key}</td>
                <td className="px-4 py-3 font-mono text-body">{r.value}</td>
                <td className="px-4 py-3">
                  <span
                    className={`px-2 py-0.5 rounded text-xs ${
                      r.scope === 'build'
                        ? 'bg-orange-100 text-orange-700'
                        : 'bg-blue-100 text-blue-700'
                    }`}
                  >
                    {r.scope}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => delMut.mutate(r.key)}
                    className="text-faint hover:text-red-600 dark:hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {envRows.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-faint">
                  No environment variables set
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Domains Tab ──────────────────────────────────────────────

function DNSRecordTable({ records }: { records: DNSRecord[] }) {
  if (!records || records.length === 0) return null;

  const isRecommended = (purpose: string) => purpose.toLowerCase().startsWith('recommended');
  const isRequired = (purpose: string) => purpose.toLowerCase().startsWith('required');

  return (
    <div className="mt-3 rounded-lg border border-amber-200 dark:border-amber-800/50 bg-amber-50/50 dark:bg-amber-900/10 overflow-hidden">
      <div className="px-3 py-2 bg-amber-100/50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800/50">
        <p className="text-xs font-medium text-amber-800 dark:text-amber-300">
          Add these records at your domain registrar (GoDaddy, Cloudflare, Namecheap, etc.)
        </p>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-amber-700 dark:text-amber-400">
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Name / Host</th>
            <th className="px-3 py-2 font-medium">Value / Target</th>
            <th className="px-3 py-2 font-medium">Note</th>
            <th className="px-3 py-2 w-8"></th>
          </tr>
        </thead>
        <tbody>
          {records.map((r, i) => (
            <tr
              key={i}
              className={clsx(
                'border-t border-amber-200/50 dark:border-amber-800/30',
                !isRecommended(r.purpose) && !isRequired(r.purpose) && 'opacity-60'
              )}
            >
              <td className="px-3 py-2">
                <span className={clsx(
                  'inline-block px-1.5 py-0.5 rounded text-[10px] font-bold',
                  r.type === 'A' && 'bg-blue-200 dark:bg-blue-800 text-blue-800 dark:text-blue-200',
                  r.type === 'CNAME' && 'bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200',
                  r.type === 'TXT' && 'bg-purple-200 dark:bg-purple-800 text-purple-800 dark:text-purple-200',
                )}>
                  {r.type}
                </span>
              </td>
              <td className="px-3 py-2 font-mono text-body break-all">{r.name}</td>
              <td className="px-3 py-2 font-mono text-body break-all">{r.value}</td>
              <td className="px-3 py-2 text-amber-700 dark:text-amber-400 max-w-[200px]">
                {isRecommended(r.purpose) && (
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle className="w-3 h-3 text-green-600 flex-shrink-0" />
                    {r.purpose}
                  </span>
                )}
                {isRequired(r.purpose) && (
                  <span className="inline-flex items-center gap-1">
                    <AlertCircle className="w-3 h-3 text-amber-600 flex-shrink-0" />
                    {r.purpose}
                  </span>
                )}
                {!isRecommended(r.purpose) && !isRequired(r.purpose) && (
                  <span className="text-muted italic">{r.purpose}</span>
                )}
              </td>
              <td className="px-3 py-2">
                <CopyButton text={r.value} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="px-3 py-2 text-[10px] text-amber-600 dark:text-amber-500 border-t border-amber-200/50 dark:border-amber-800/30">
        Choose either A or CNAME (not both). TXT record is always required. DNS can take up to 48 hours to propagate.
      </div>
    </div>
  );
}

function DomainCard({
  domain,
  onVerify,
  onRemove,
  isVerifying,
}: {
  domain: DomainResponse;
  onVerify: () => void;
  onRemove: () => void;
  isVerifying: boolean;
}) {
  const [showDns, setShowDns] = useState(!domain.verified && domain.dns_records.length > 0);

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {/* Status icon */}
          <div className={clsx(
            'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5',
            domain.is_platform
              ? 'bg-blue-50 dark:bg-blue-900/20'
              : domain.verified
                ? 'bg-green-50 dark:bg-green-900/20'
                : 'bg-amber-50 dark:bg-amber-900/20'
          )}>
            {domain.is_platform ? (
              <Globe className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            ) : domain.verified ? (
              <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
            ) : (
              <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            )}
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm text-body truncate">{domain.domain}</span>
              <CopyButton text={domain.domain} />
            </div>
            {domain.is_platform ? (
              <p className="text-xs text-muted mt-0.5">Platform subdomain (always active)</p>
            ) : domain.verified ? (
              <p className="text-xs text-green-600 dark:text-green-400 mt-0.5">DNS verified</p>
            ) : (
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">Pending DNS configuration</p>
            )}
          </div>
        </div>

        {/* Actions */}
        {!domain.is_platform && (
          <div className="flex items-center gap-2 flex-shrink-0">
            {!domain.verified && domain.dns_records.length > 0 && (
              <button
                onClick={() => setShowDns(!showDns)}
                className="text-xs text-muted hover:text-body"
              >
                {showDns ? 'Hide DNS' : 'Show DNS'}
              </button>
            )}
            <button
              onClick={onVerify}
              disabled={isVerifying}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 disabled:opacity-50"
            >
              {isVerifying ? 'Checking...' : 'Check DNS'}
            </button>
            <button
              onClick={onRemove}
              className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400"
            >
              Remove
            </button>
          </div>
        )}
      </div>

      {/* DNS records panel */}
      {showDns && !domain.is_platform && domain.dns_records.length > 0 && (
        <DNSRecordTable records={domain.dns_records} />
      )}
    </div>
  );
}

function PlatformDomainCard({ site, platformDomain }: { site?: Site; platformDomain: DomainResponse }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [newSlug, setNewSlug] = useState(site?.slug ?? '');

  const updateMut = useMutation({
    mutationFn: () => api.updateSite(site!.id, { slug: newSlug } as Partial<Site>),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['site', site!.id] });
      qc.invalidateQueries({ queryKey: ['domains', site!.id] });
      setEditing(false);
    },
  });

  // Parse the platform domain to highlight the slug part
  // Format: slug.workspace.tenant.platformdomain.com
  const parts = platformDomain.domain.split('.');
  const slugPart = parts[0];
  const restPart = '.' + parts.slice(1).join('.');

  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5 bg-blue-50 dark:bg-blue-900/20">
            <Globe className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          </div>
          <div className="min-w-0">
            {editing ? (
              <div className="flex items-center gap-1">
                <input
                  value={newSlug}
                  onChange={e => setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  className="border rounded px-2 py-1 text-sm font-mono dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 w-40"
                  autoFocus
                />
                <span className="text-sm font-mono text-muted">{restPart}</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-body">
                  <strong className="text-heading">{slugPart}</strong>
                  <span className="text-muted">{restPart}</span>
                </span>
                <CopyButton text={platformDomain.domain} />
              </div>
            )}
            <p className="text-xs text-muted mt-0.5">Platform subdomain (always active)</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {editing ? (
            <>
              <button
                onClick={() => updateMut.mutate()}
                disabled={!newSlug || newSlug === slugPart || updateMut.isPending}
                className="text-xs bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {updateMut.isPending ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={() => { setEditing(false); setNewSlug(slugPart); }}
                className="text-xs text-muted hover:text-body"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => { setNewSlug(slugPart); setEditing(true); }}
              className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
            >
              Edit
            </button>
          )}
        </div>
      </div>
      {updateMut.isError && (
        <p className="text-xs text-red-600 dark:text-red-400 mt-2">
          {(updateMut.error as Error)?.message ?? 'Failed to update slug'}
        </p>
      )}
    </div>
  );
}

function DomainsTab({ siteId, site }: { siteId: string; site?: Site }) {
  const qc = useQueryClient();
  const { data: domains } = useQuery({
    queryKey: ['domains', siteId],
    queryFn: () => api.listDomains(siteId),
  });
  const [domain, setDomain] = useState('');

  const addMut = useMutation({
    mutationFn: () => api.addDomain(siteId, domain),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['domains', siteId] });
      setDomain('');
    },
  });
  const removeMut = useMutation({
    mutationFn: (d: string) => api.removeDomain(siteId, d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['domains', siteId] }),
  });
  const verifyMut = useMutation({
    mutationFn: (d: string) => api.verifyDomain(siteId, d),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['domains', siteId] }),
  });

  const platformDomain = domains?.find(d => d.is_platform);
  const customDomains = domains?.filter(d => !d.is_platform) ?? [];

  return (
    <div className="space-y-4">
      {/* Platform subdomain */}
      {platformDomain && (
        <div>
          <h3 className="text-label text-xs mb-2 uppercase tracking-wider">Platform Domain</h3>
          <PlatformDomainCard site={site} platformDomain={platformDomain} />
        </div>
      )}

      {/* Custom domains section */}
      <div>
        <h3 className="text-label text-xs mb-2 uppercase tracking-wider">Custom Domains</h3>

        {/* Add domain form */}
        <div className="card p-4 mb-3">
          <div className="flex gap-2">
            <input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && domain) addMut.mutate(); }}
              placeholder="app.example.com"
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 dark:bg-gray-800 dark:text-gray-200 font-mono"
            />
            <button
              onClick={() => addMut.mutate()}
              disabled={!domain || addMut.isPending}
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              Add Domain
            </button>
          </div>
          {addMut.isError && (
            <p className="text-xs text-red-600 dark:text-red-400 mt-2">
              {(addMut.error as Error)?.message ?? 'Failed to add domain'}
            </p>
          )}
        </div>

        {/* Custom domain cards */}
        {customDomains.length > 0 ? (
          <div className="space-y-3">
            {customDomains.map((d) => (
              <DomainCard
                key={d.domain}
                domain={d}
                onVerify={() => verifyMut.mutate(d.domain)}
                onRemove={() => removeMut.mutate(d.domain)}
                isVerifying={verifyMut.isPending && verifyMut.variables === d.domain}
              />
            ))}
          </div>
        ) : (
          <div className="card p-6 text-center">
            <Globe className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-muted">No custom domains configured</p>
            <p className="text-xs text-faint mt-1">Add a domain above to get DNS configuration instructions</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Health Tab ───────────────────────────────────────────────

function HealthTab({ siteId }: { siteId: string }) {
  const { data: health } = useQuery({
    queryKey: ['health-history', siteId],
    queryFn: () => api.getHealthHistory(siteId),
    refetchInterval: 10000,
  });

  const statusColor = (status?: string) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-100 text-green-700';
      case 'degraded':
        return 'bg-yellow-100 text-yellow-700';
      case 'down':
        return 'bg-red-100 text-red-700';
      default:
        return 'bg-gray-100 text-gray-600';
    }
  };

  return (
    <div>
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Health Status</p>
          <span
            className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(
              health?.health_status
            )}`}
          >
            {health?.health_status || 'unknown'}
          </span>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Failure Count</p>
          <p className="text-lg text-heading">
            {health?.health_failure_count ?? 0}
          </p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Last Check</p>
          <p className="text-sm text-label">{relativeTime(health?.last_health_check)}</p>
        </div>
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">Last Healthy</p>
          <p className="text-sm text-label">{relativeTime(health?.last_healthy_at)}</p>
        </div>
      </div>

      {/* Events table */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="thead">
            <tr>
              <th className="px-4 py-3 font-medium">Check Time</th>
              <th className="px-4 py-3 font-medium">Status Code</th>
              <th className="px-4 py-3 font-medium">Response</th>
              <th className="px-4 py-3 font-medium">Healthy</th>
              <th className="px-4 py-3 font-medium">Action Taken</th>
            </tr>
          </thead>
          <tbody className="tbody">
            {health?.recent_events?.map((evt: HealthEvent) => (
              <tr key={evt.id}>
                <td className="px-4 py-3 text-xs text-muted">
                  {relativeTime(evt.check_time)}
                </td>
                <td className="px-4 py-3 font-mono">{evt.status_code ?? '\u2014'}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  {evt.response_ms != null ? `${evt.response_ms}ms` : '\u2014'}
                </td>
                <td className="px-4 py-3">
                  {evt.healthy ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-muted">
                  {evt.action_taken || '\u2014'}
                </td>
              </tr>
            ))}
            {(!health?.recent_events || health.recent_events.length === 0) && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-faint">
                  No health events recorded
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Linked Services Tab ──────────────────────────────────────

function LinkedServicesTab({ siteId }: { siteId: string }) {
  const qc = useQueryClient();
  const { data: services } = useQuery({
    queryKey: ['linked-services', siteId],
    queryFn: () => api.listLinkedServices(siteId),
  });
  const [serviceType, setServiceType] = useState('postgres');
  const [showAdd, setShowAdd] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const createMut = useMutation({
    mutationFn: () => api.createLinkedService(siteId, { service_type: serviceType }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linked-services', siteId] });
      setShowAdd(false);
    },
  });
  const deleteMut = useMutation({
    mutationFn: (serviceId: string) => api.deleteLinkedService(siteId, serviceId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['linked-services', siteId] });
      setConfirmDelete(null);
    },
  });

  const ServiceIcon = ({ type }: { type: string }) => {
    if (type === 'postgres' || type === 'postgresql') return <Database className="w-4 h-4 text-blue-500" />;
    if (type === 'redis') return <Zap className="w-4 h-4 text-red-500" />;
    return <Database className="w-4 h-4 text-gray-400" />;
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-heading">Linked Services</h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 rounded text-sm hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> Add Service
        </button>
      </div>

      {showAdd && (
        <div className="card p-5 mb-4">
          <h4 className="text-sm text-heading mb-3">Add Linked Service</h4>
          <div className="flex gap-2">
            <select
              value={serviceType}
              onChange={(e) => setServiceType(e.target.value)}
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 dark:bg-gray-800 dark:text-gray-200"
            >
              <option value="postgres">PostgreSQL</option>
              <option value="redis">Redis</option>
            </select>
            <button
              onClick={() => createMut.mutate()}
              disabled={createMut.isPending}
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {createMut.isPending ? 'Creating...' : 'Create'}
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="border dark:border-gray-600 rounded px-4 py-2 text-sm text-body hover:bg-gray-50 dark:hover:bg-gray-800/30"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {services?.map((svc: LinkedService) => (
          <div key={svc.id} className="card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <ServiceIcon type={svc.service_type} />
                <div>
                  <p className="text-sm font-medium">
                    {svc.name || svc.service_type}
                  </p>
                  <p className="text-xs text-muted capitalize">{svc.service_type}</p>
                </div>
                <StatusBadge status={svc.status} />
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setExpandedId(expandedId === svc.id ? null : svc.id)
                  }
                  className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                >
                  {expandedId === svc.id ? 'Hide Env' : 'Show Env'}
                </button>
                {confirmDelete === svc.id ? (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-red-600 dark:text-red-400">Delete?</span>
                    <button
                      onClick={() => deleteMut.mutate(svc.id)}
                      className="text-xs text-red-600 font-medium hover:text-red-800"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setConfirmDelete(null)}
                      className="text-xs text-muted hover:text-gray-700 dark:hover:text-gray-300"
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmDelete(svc.id)}
                    className="text-faint hover:text-red-600 dark:hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
            {expandedId === svc.id && svc.connection_env && (
              <div className="mt-3 bg-gray-50 dark:bg-gray-800/50 rounded p-3">
                <p className="text-xs font-medium text-muted mb-2">Connection Environment Variables</p>
                <div className="space-y-1">
                  {Object.entries(svc.connection_env).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2 text-xs font-mono">
                      <span className="text-body">{k}=</span>
                      <span className="text-heading">{v}</span>
                      <CopyButton text={`${k}=${v}`} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
        {(!services || services.length === 0) && (
          <div className="card p-6 text-center text-faint">
            No linked services. Add a database or cache to get started.
          </div>
        )}
      </div>
    </div>
  );
}

// ── Notifications Tab ────────────────────────────────────────

const NOTIFICATION_EVENTS = [
  'deploy.started',
  'deploy.succeeded',
  'deploy.failed',
  'health.down',
  'health.recovered',
  'preview.created',
  'preview.destroyed',
];

function NotificationsTab({ siteId }: { siteId: string }) {
  const qc = useQueryClient();
  const { data: notifications } = useQuery({
    queryKey: ['notifications', siteId],
    queryFn: () => api.listNotifications(siteId),
  });
  const [showAdd, setShowAdd] = useState(false);
  const [newType, setNewType] = useState('webhook');
  const [newTarget, setNewTarget] = useState('');
  const [newName, setNewName] = useState('');
  const [newEvents, setNewEvents] = useState<string[]>([]);

  const createMut = useMutation({
    mutationFn: () =>
      api.createNotification(siteId, {
        type: newType,
        target: newTarget,
        name: newName || undefined,
        events: newEvents.length > 0 ? newEvents : undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications', siteId] });
      setShowAdd(false);
      setNewTarget('');
      setNewName('');
      setNewEvents([]);
    },
  });
  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api.updateNotification(id, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications', siteId] }),
  });
  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteNotification(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications', siteId] }),
  });

  const TypeIcon = ({ type }: { type: string }) => {
    switch (type) {
      case 'webhook':
        return <Globe className="w-4 h-4 text-blue-500" />;
      case 'slack':
        return <Hash className="w-4 h-4 text-purple-500" />;
      case 'email':
        return <Mail className="w-4 h-4 text-green-500" />;
      default:
        return <Bell className="w-4 h-4 text-gray-400" />;
    }
  };

  const toggleEvent = (event: string) => {
    setNewEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-heading">Notifications</h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 rounded text-sm hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> Add Notification
        </button>
      </div>

      {showAdd && (
        <div className="card p-5 mb-4">
          <h4 className="text-sm text-heading mb-3">Add Notification</h4>
          <div className="space-y-3">
            <div className="flex gap-2">
              <select
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                className="border rounded px-3 py-2 text-sm"
              >
                <option value="webhook">Webhook</option>
                <option value="slack">Slack</option>
                <option value="email">Email</option>
              </select>
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Name (optional)"
                className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 dark:bg-gray-800 dark:text-gray-200"
              />
            </div>
            <input
              type="text"
              value={newTarget}
              onChange={(e) => setNewTarget(e.target.value)}
              placeholder={
                newType === 'email'
                  ? 'user@example.com'
                  : newType === 'slack'
                    ? '#channel or webhook URL'
                    : 'https://example.com/webhook'
              }
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm w-full dark:bg-gray-800 dark:text-gray-200"
            />
            <div>
              <p className="text-xs font-medium text-muted mb-2">Events</p>
              <div className="flex flex-wrap gap-2">
                {NOTIFICATION_EVENTS.map((event) => (
                  <label
                    key={event}
                    className="flex items-center gap-1.5 text-xs cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={newEvents.includes(event)}
                      onChange={() => toggleEvent(event)}
                      className="rounded border-gray-300"
                    />
                    <span>{event}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => createMut.mutate()}
                disabled={!newTarget || createMut.isPending}
                className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {createMut.isPending ? 'Creating...' : 'Create'}
              </button>
              <button
                onClick={() => setShowAdd(false)}
                className="border dark:border-gray-600 rounded px-4 py-2 text-sm text-body hover:bg-gray-50 dark:hover:bg-gray-800/30"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {notifications?.map((n: NotificationConfig) => (
          <div key={n.id} className="card p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <TypeIcon type={n.type} />
                <div>
                  <p className="text-sm font-medium">{n.name || n.type}</p>
                  <p className="text-xs text-muted font-mono truncate max-w-xs">
                    {n.target}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() =>
                    toggleMut.mutate({ id: n.id, enabled: !n.enabled })
                  }
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    n.enabled ? 'bg-blue-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                      n.enabled ? 'translate-x-4.5' : 'translate-x-0.5'
                    }`}
                  />
                </button>
                <button
                  onClick={() => deleteMut.mutate(n.id)}
                  className="text-faint hover:text-red-600 dark:hover:text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            {n.events && n.events.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {n.events.map((event) => (
                  <span
                    key={event}
                    className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700 text-body"
                  >
                    {event}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
        {(!notifications || notifications.length === 0) && (
          <div className="card p-6 text-center text-faint">
            No notification channels configured
          </div>
        )}
      </div>
    </div>
  );
}

// ── Previews Tab ─────────────────────────────────────────────

function PreviewsTab({ siteId }: { siteId: string }) {
  const qc = useQueryClient();
  const { data: previews } = useQuery({
    queryKey: ['previews', siteId],
    queryFn: () => api.listPreviews(siteId),
    refetchInterval: 10000,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deletePreview(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['previews', siteId] }),
  });

  if (!previews || previews.length === 0) {
    return (
      <div className="card p-8 text-center">
        <Layers className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
        <h3 className="font-medium text-label mb-1">No active previews</h3>
        <p className="text-sm text-muted max-w-md mx-auto">
          Preview environments are automatically created when pull requests are opened against
          this site's repository. Configure a webhook in the Git Config tab to enable automatic previews.
        </p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="thead">
          <tr>
            <th className="px-4 py-3 font-medium">PR</th>
            <th className="px-4 py-3 font-medium">Branch</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Preview URL</th>
            <th className="px-4 py-3 font-medium">Commit</th>
            <th className="px-4 py-3 font-medium">Created</th>
            <th className="px-4 py-3 w-20"></th>
          </tr>
        </thead>
        <tbody className="tbody">
          {previews.map((p: PreviewEnvironment) => (
            <tr key={p.id}>
              <td className="px-4 py-3">
                <div>
                  <span className="font-medium">#{p.pr_number}</span>
                  {p.pr_title && (
                    <p className="text-xs text-muted truncate max-w-xs">{p.pr_title}</p>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex items-center gap-1 text-xs font-mono bg-gray-100 dark:bg-gray-700 dark:text-gray-300 rounded px-2 py-0.5">
                  <GitBranch className="w-3 h-3" />
                  {p.pr_branch}
                </span>
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={p.status} />
              </td>
              <td className="px-4 py-3">
                {p.preview_url ? (
                  <a
                    href={p.preview_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 text-xs font-mono flex items-center gap-1"
                  >
                    {p.preview_url} <ExternalLink className="w-3 h-3" />
                  </a>
                ) : (
                  <span className="text-faint text-xs">{'\u2014'}</span>
                )}
              </td>
              <td className="px-4 py-3 font-mono text-xs">
                {p.commit_sha ? p.commit_sha.slice(0, 8) : '\u2014'}
              </td>
              <td className="px-4 py-3 text-xs text-muted">
                {relativeTime(p.created_at)}
              </td>
              <td className="px-4 py-3">
                {p.status === 'running' || p.status === 'active' || p.status === 'live' ? (
                  <button
                    onClick={() => deleteMut.mutate(p.id)}
                    disabled={deleteMut.isPending}
                    className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                  >
                    Destroy
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Deployments Tab ──────────────────────────────────────────

function DeploymentsTab({ siteId }: { siteId: string }) {
  const { data: deployments } = useQuery({
    queryKey: ['deployments', siteId],
    queryFn: () => api.listDeployments(siteId),
  });

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="thead">
          <tr>
            <th className="px-4 py-3 font-medium">Version</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Image</th>
            <th className="px-4 py-3 font-medium">Port</th>
            <th className="px-4 py-3 font-medium">Deployed</th>
          </tr>
        </thead>
        <tbody className="tbody">
          {deployments?.map((d: Deployment) => (
            <tr key={d.id}>
              <td className="px-4 py-3 font-mono">v{d.version}</td>
              <td className="px-4 py-3">
                <StatusBadge status={d.status} />
              </td>
              <td className="px-4 py-3 font-mono text-xs text-muted">
                {d.image_tag ?? '\u2014'}
              </td>
              <td className="px-4 py-3 font-mono">{d.host_port ?? '\u2014'}</td>
              <td className="px-4 py-3 text-muted text-xs">
                {d.deployed_at ? new Date(d.deployed_at).toLocaleString() : '\u2014'}
              </td>
            </tr>
          ))}
          {(!deployments || deployments.length === 0) && (
            <tr>
              <td colSpan={5} className="px-4 py-6 text-center text-faint">
                No deployments yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

// ── Logs Tab ─────────────────────────────────────────────────

function LogsTab({ siteId, site }: { siteId: string; site?: Site }) {
  const { data, refetch, isFetching, isError, error } = useQuery({
    queryKey: ['logs', siteId],
    queryFn: () => api.getSiteLogs(siteId, 200),
    retry: false,
  });

  const lines = data?.lines ?? [];
  const hasLines = lines.length > 0;
  const isErrorState = site?.status === 'error';

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-1.5 bg-gray-800 text-white px-4 py-2 rounded-lg text-sm hover:bg-gray-700 active:bg-gray-900 disabled:opacity-50"
        >
          <RefreshCw className={clsx('w-4 h-4', isFetching && 'animate-spin')} />
          {isFetching ? 'Loading...' : 'Refresh Logs'}
        </button>
      </div>

      {isErrorState && !hasLines && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
          <div className="flex items-start gap-2">
            <XCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-800 dark:text-red-300">Container failed to start</p>
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">
                The container is in an error state and has no logs. This usually means it failed during startup
                (e.g., port conflict, image pull failure, or crash on boot). Try "Rebuild &amp; Deploy" to redeploy,
                or check the Pipelines tab for build errors.
              </p>
            </div>
          </div>
        </div>
      )}

      {isError && (
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3 mb-4">
          <p className="text-xs text-amber-700 dark:text-amber-400">
            Failed to fetch logs: {(error as Error)?.message ?? 'Unknown error'}
          </p>
        </div>
      )}

      <div className="bg-gray-900 text-green-400 rounded-lg p-4 font-mono text-xs overflow-auto max-h-[600px]">
        {hasLines ? (
          lines.map((line, i) => (
            <div key={i} className="leading-5">
              {line}
            </div>
          ))
        ) : (
          !isFetching && (
            <p className="text-gray-500">
              {isErrorState ? 'No container logs available.' : 'No logs yet. Container may still be starting.'}
            </p>
          )
        )}
      </div>
    </div>
  );
}

// ── Members Tab ──────────────────────────────────────────────

const SITE_ROLES = ['site_admin', 'site_deployer', 'site_viewer'];

function MembersTab({ siteId }: { siteId: string }) {
  const qc = useQueryClient();
  const { data: members } = useQuery({
    queryKey: ['site-members', siteId],
    queryFn: () => api.listSiteMembers(siteId),
  });
  const [showAdd, setShowAdd] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('site_viewer');

  const addMut = useMutation({
    mutationFn: () =>
      api.addSiteMember(siteId, {
        user_id: '',
        user_email: newEmail,
        role: newRole,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['site-members', siteId] });
      setShowAdd(false);
      setNewEmail('');
      setNewRole('site_viewer');
    },
  });
  const updateMut = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.updateSiteMember(siteId, userId, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site-members', siteId] }),
  });
  const removeMut = useMutation({
    mutationFn: (userId: string) => api.removeSiteMember(siteId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['site-members', siteId] }),
  });

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-heading">Site Members</h3>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 bg-blue-600 text-white px-3 py-2 rounded text-sm hover:bg-blue-700"
        >
          <Plus className="w-4 h-4" /> Add Member
        </button>
      </div>

      {showAdd && (
        <div className="card p-5 mb-4">
          <h4 className="text-sm text-heading mb-3">Add Member</h4>
          <div className="flex gap-2">
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="user@example.com"
              className="border dark:border-gray-600 rounded px-3 py-2 text-sm flex-1 dark:bg-gray-800 dark:text-gray-200"
            />
            <select
              value={newRole}
              onChange={(e) => setNewRole(e.target.value)}
              className="border rounded px-3 py-2 text-sm"
            >
              {SITE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.replace('site_', '').replace(/^\w/, (c) => c.toUpperCase())}
                </option>
              ))}
            </select>
            <button
              onClick={() => addMut.mutate()}
              disabled={!newEmail || addMut.isPending}
              className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {addMut.isPending ? 'Adding...' : 'Add'}
            </button>
            <button
              onClick={() => setShowAdd(false)}
              className="border dark:border-gray-600 rounded px-4 py-2 text-sm text-body hover:bg-gray-50 dark:hover:bg-gray-800/30"
            >
              Cancel
            </button>
          </div>
          {addMut.isError && (
            <p className="mt-2 text-sm text-red-600">
              Error: {(addMut.error as Error).message}
            </p>
          )}
        </div>
      )}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="thead">
            <tr>
              <th className="px-4 py-3 font-medium">Email</th>
              <th className="px-4 py-3 font-medium">Role</th>
              <th className="px-4 py-3 font-medium">Added</th>
              <th className="px-4 py-3 w-12"></th>
            </tr>
          </thead>
          <tbody className="tbody">
            {members?.map((m: Membership) => (
              <tr key={m.id}>
                <td className="px-4 py-3">{m.user_email}</td>
                <td className="px-4 py-3">
                  <select
                    value={m.role}
                    onChange={(e) =>
                      updateMut.mutate({ userId: m.user_id, role: e.target.value })
                    }
                    className="border dark:border-gray-600 rounded px-2 py-1 text-xs dark:bg-gray-800 dark:text-gray-200"
                  >
                    {SITE_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r.replace('site_', '').replace(/^\w/, (c) => c.toUpperCase())}
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-4 py-3 text-xs text-muted">
                  {relativeTime(m.created_at)}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => removeMut.mutate(m.user_id)}
                    className="text-faint hover:text-red-600 dark:hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
            {(!members || members.length === 0) && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-faint">
                  No site-level members
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

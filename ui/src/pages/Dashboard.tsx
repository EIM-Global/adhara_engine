import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { SiteSummary, PipelineRunSummary } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import {
  Building2,
  Globe,
  Server,
  Activity,
  GitCommit,
  Rocket,
  AlertTriangle,
  HeartPulse,
} from 'lucide-react';

// ---- helpers ----------------------------------------------------------------

function timeAgo(iso: string): string {
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ---- component --------------------------------------------------------------

export default function Dashboard() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health });
  const { data: tenants } = useQuery({ queryKey: ['tenants'], queryFn: api.listTenants });
  const { data: ports } = useQuery({ queryKey: ['ports'], queryFn: api.listPorts });
  const { data: sites } = useQuery({
    queryKey: ['all-sites'],
    queryFn: api.listAllSites,
    refetchInterval: 15000,
  });

  const allSites: SiteSummary[] = sites ?? [];
  const running = (ports as { status?: string }[] | undefined)?.filter(
    (p) => p.status === 'running',
  ).length ?? 0;
  const totalSites = (ports as unknown[] | undefined)?.length ?? 0;

  const siteIds = allSites.map((s) => s.id).sort();
  const { data: pipelinesBySite } = useQuery({
    queryKey: ['dashboard-pipelines', siteIds],
    queryFn: async () => {
      if (siteIds.length === 0) return {} as Record<string, PipelineRunSummary[]>;
      const entries = await Promise.all(
        siteIds.map(async (id) => {
          try {
            const runs = await api.listPipelines(id);
            return [id, runs] as const;
          } catch {
            return [id, []] as const;
          }
        }),
      );
      return Object.fromEntries(entries) as Record<string, PipelineRunSummary[]>;
    },
    enabled: siteIds.length > 0,
    refetchInterval: 20000,
  });

  const siteMap = new Map(allSites.map((s) => [s.id, s]));
  const recentPipelines: (PipelineRunSummary & { siteName: string; siteId: string })[] = [];
  if (pipelinesBySite) {
    for (const [siteId, runs] of Object.entries(pipelinesBySite)) {
      const site = siteMap.get(siteId);
      for (const run of runs) {
        recentPipelines.push({ ...run, siteName: site?.name ?? 'Unknown', siteId });
      }
    }
  }
  recentPipelines.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  const top10 = recentPipelines.slice(0, 10);

  const healthIssues = allSites.filter(
    (s) => s.status === 'error' || s.status === 'failed',
  );

  return (
    <div className="p-6 lg:p-8">
      <h1 className="text-heading text-2xl mb-6">Dashboard</h1>

      {/* ---- Stat cards ---- */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Activity} label="Status" value={health?.status ?? '...'} color="green" />
        <StatCard icon={Building2} label="Tenants" value={tenants?.length ?? '...'} color="blue" />
        <StatCard icon={Globe} label="Sites" value={totalSites} color="purple" />
        <StatCard icon={Server} label="Running" value={running} color="green" />
      </div>

      {/* ---- System Info ---- */}
      <div className="card p-5 mb-8">
        <h2 className="text-heading text-lg mb-3">System Info</h2>
        <div className="text-sm text-body space-y-1">
          <p>Version: {health?.version ?? '...'}</p>
          <p>Service: {health?.service ?? '...'}</p>
        </div>
      </div>

      {/* ---- Recent Pipelines ---- */}
      <div className="card p-5 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <div className="icon-box-blue">
            <Rocket className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          </div>
          <h2 className="text-heading text-lg">Recent Pipelines</h2>
        </div>

        {top10.length === 0 ? (
          <div className="text-center py-8">
            <GitCommit className="w-8 h-8 text-faint mx-auto mb-2" />
            <p className="text-sm text-muted">
              Deploy a site to see pipeline activity.{' '}
              <Link to="/sites" className="link">View sites</Link>
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-5">
            <table className="w-full text-sm">
              <thead className="thead">
                <tr>
                  <th className="px-5 py-3 font-medium">Site</th>
                  <th className="px-5 py-3 font-medium">Trigger</th>
                  <th className="px-5 py-3 font-medium">Commit</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">When</th>
                </tr>
              </thead>
              <tbody className="tbody">
                {top10.map((run) => (
                  <tr key={run.id} className="trow">
                    <td className="px-5 py-3">
                      <Link to={`/sites/${run.siteId}`} className="link">
                        {run.siteName}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-body">{run.trigger}</td>
                    <td className="px-5 py-3 font-mono text-xs text-muted">
                      {run.commit_sha ? run.commit_sha.slice(0, 8) : '--'}
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-5 py-3 text-muted text-xs">
                      {timeAgo(run.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ---- Health Overview ---- */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <div className="icon-box-red">
            <HeartPulse className="w-4 h-4 text-red-500 dark:text-red-400" />
          </div>
          <h2 className="text-heading text-lg">Health Overview</h2>
        </div>

        {healthIssues.length === 0 ? (
          <div className="text-center py-8">
            <Activity className="w-8 h-8 text-faint mx-auto mb-2" />
            <p className="text-sm text-muted">All sites are healthy.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {healthIssues.map((site) => (
              <Link
                key={site.id}
                to={`/sites/${site.id}`}
                className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 rounded-xl p-4 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-500 dark:text-red-400 mt-0.5 flex-shrink-0" />
                  <div className="min-w-0">
                    <p className="text-heading truncate">{site.name}</p>
                    <div className="mt-1">
                      <StatusBadge status={site.status} />
                    </div>
                    <p className="text-xs text-muted mt-2">
                      {site.tenant_slug} / {site.workspace_slug}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---- StatCard ---------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  color: string;
}) {
  const iconBoxClass: Record<string, string> = {
    green: 'icon-box-green',
    blue: 'icon-box-blue',
    purple: 'icon-box-purple',
  };
  const iconColor: Record<string, string> = {
    green: 'text-green-600 dark:text-green-400',
    blue: 'text-blue-600 dark:text-blue-400',
    purple: 'text-purple-600 dark:text-purple-400',
  };
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3">
        <div className={`p-2.5 rounded-xl ${iconBoxClass[color] ?? 'icon-box-blue'}`}>
          <Icon className={`w-5 h-5 ${iconColor[color] ?? iconColor.blue}`} />
        </div>
        <div>
          <p className="text-sm text-muted">{label}</p>
          <p className="text-2xl text-heading">{value}</p>
        </div>
      </div>
    </div>
  );
}

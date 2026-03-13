import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { SiteSummary } from '../api/client';
import { ExternalLink, Layers } from 'lucide-react';
import clsx from 'clsx';

function StatusBadge({ status }: { status: string }) {
  const isRunning = status === 'running';
  const isError = status === 'error';
  const isDeploying = status === 'deploying' || status === 'building';

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        isRunning && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
        isError && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
        isDeploying && 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
        !isRunning && !isError && !isDeploying && 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
      )}
    >
      <span
        className={clsx(
          'w-1.5 h-1.5 rounded-full',
          isRunning && 'bg-green-500',
          isError && 'bg-red-500',
          isDeploying && 'bg-yellow-500 animate-pulse',
          !isRunning && !isError && !isDeploying && 'bg-gray-400 dark:bg-gray-500',
        )}
      />
      {status}
    </span>
  );
}

function siteUrl(site: SiteSummary): string {
  return `http://${site.slug}.${site.workspace_slug}.${site.tenant_slug}.localhost`;
}

export default function Sites() {
  const { data: sites, isLoading } = useQuery({
    queryKey: ['all-sites'],
    queryFn: api.listAllSites,
    refetchInterval: 10000,
  });

  const allSites = sites ?? [];
  const runningCount = allSites.filter(s => s.status === 'running').length;
  const stoppedCount = allSites.filter(s => s.status === 'stopped').length;

  // Group by tenant
  const grouped: Record<string, SiteSummary[]> = {};
  for (const s of allSites) {
    const key = s.tenant_slug;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(s);
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-heading text-2xl">Sites</h1>
          <p className="text-sm text-muted mt-1">
            {allSites.length} total &middot; {runningCount} running
            {stoppedCount > 0 && ` \u00b7 ${stoppedCount} stopped`}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-muted text-sm">Loading sites...</div>
      ) : allSites.length === 0 ? (
        <div className="card p-8 text-center">
          <Layers className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-label mb-1">No sites yet</h3>
          <p className="text-sm text-muted">
            Create a site from a <Link to="/tenants" className="link">workspace</Link> to get started.
          </p>
        </div>
      ) : (
        Object.entries(grouped).map(([tenantSlug, tenantSites]) => (
          <div key={tenantSlug} className="mb-8">
            <h2 className="section-label mb-3">
              {tenantSlug}
            </h2>
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="thead">
                  <tr>
                    <th className="px-4 py-3 font-medium">Site</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Workspace</th>
                    <th className="px-4 py-3 font-medium">URL</th>
                    <th className="px-4 py-3 font-medium">Port</th>
                    <th className="px-4 py-3 w-12"></th>
                  </tr>
                </thead>
                <tbody className="tbody">
                  {tenantSites.map(site => {
                    const url = siteUrl(site);
                    const isRunning = site.status === 'running';

                    return (
                      <tr key={site.id} className="trow">
                        <td className="px-4 py-3">
                          <Link to={`/sites/${site.id}`} className="link">
                            {site.name}
                          </Link>
                          <p className="text-xs text-faint font-mono">{site.slug}</p>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={site.status} />
                        </td>
                        <td className="px-4 py-3 text-muted font-mono text-xs">
                          {site.workspace_slug}
                        </td>
                        <td className="px-4 py-3">
                          {isRunning ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-mono inline-flex items-center gap-1"
                            >
                              {url}
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          ) : (
                            <span className="text-xs text-faint font-mono">{url}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 font-mono text-muted">
                          {site.host_port ?? '—'}
                        </td>
                        <td className="px-4 py-3">
                          {isRunning && (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-gray-400 dark:text-gray-500 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
                              title="Open site"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

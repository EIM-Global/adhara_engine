import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { RegistryRepo } from '../api/client';
import {
  Package, Tag, Layers, ExternalLink, CheckCircle2, XCircle,
  Terminal, Copy, Check, ChevronRight,
} from 'lucide-react';
import { useState } from 'react';
import { useRegistryHost } from '../hooks/useRegistryHost';

function CopyButton({ text, className = '' }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className={`p-1 rounded hover:bg-white/10 transition-colors ${className}`}
      title="Copy"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-gray-500" />}
    </button>
  );
}

function TagBadge({ tag }: { tag: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300 border border-gray-200 dark:border-gray-700">
      <Tag className="w-2.5 h-2.5 flex-shrink-0" />
      {tag}
    </span>
  );
}

function RepoCard({ repo, registryHost }: { repo: RegistryRepo; registryHost: string }) {
  const hasLinkedSite = Boolean(repo.site_id);
  const tenantWorkspacePath =
    repo.tenant_slug && repo.workspace_slug
      ? `${repo.tenant_slug} / ${repo.workspace_slug}`
      : null;

  return (
    <Link
      to={`/registry/${encodeURIComponent(repo.repository)}`}
      className="card p-4 block hover:border-blue-500/30 transition-colors group"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-blue-50 dark:bg-blue-900/20 flex items-center justify-center">
          <Package className="w-5 h-5 text-blue-600 dark:text-blue-400" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-body font-mono text-sm font-medium truncate" title={repo.repository}>
                  {repo.repository}
                </h3>
                <ChevronRight className="w-4 h-4 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
              </div>
              <p className="text-[11px] font-mono text-muted mt-0.5">
                {registryHost}/{repo.repository}
              </p>
              {hasLinkedSite ? (
                <div className="mt-1 flex items-center gap-1.5">
                  <span className="text-xs text-muted">Linked to</span>
                  <span className="link text-xs inline-flex items-center gap-1">
                    {repo.site_name ?? repo.site_slug ?? repo.site_id}
                    <ExternalLink className="w-3 h-3" />
                  </span>
                  {tenantWorkspacePath && (
                    <span className="text-xs text-muted">
                      &middot; {tenantWorkspacePath}
                    </span>
                  )}
                </div>
              ) : (
                <p className="mt-1 text-xs text-muted italic">Unlinked — available to deploy</p>
              )}
            </div>

            <div className="flex items-center gap-1 flex-shrink-0 text-xs text-muted">
              <Layers className="w-3.5 h-3.5" />
              <span>{repo.tags.length} {repo.tags.length === 1 ? 'tag' : 'tags'}</span>
            </div>
          </div>

          {repo.tags.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {repo.tags.slice(0, 8).map(tag => (
                <TagBadge key={tag} tag={tag} />
              ))}
              {repo.tags.length > 8 && (
                <span className="text-xs text-muted self-center">+{repo.tags.length - 8} more</span>
              )}
            </div>
          )}

          {repo.tags.length === 0 && (
            <p className="mt-2 text-xs text-muted italic">No tags</p>
          )}
        </div>
      </div>
    </Link>
  );
}

export default function Registry() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['registry'],
    queryFn: api.listRegistry,
    refetchInterval: 30000,
  });

  const { data: health } = useQuery({
    queryKey: ['registry-health'],
    queryFn: api.getRegistryHealth,
    refetchInterval: 60000,
  });

  const repos: RegistryRepo[] = data?.repositories ?? [];
  const registryError = data?.error;
  const totalTags = repos.reduce((sum, r) => sum + r.tags.length, 0);
  const registryHost = useRegistryHost();

  return (
    <div className="p-6">
      {/* Page header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">
            <Package className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-heading text-2xl">Docker Registry</h1>
              {health && (
                <span className="flex items-center gap-1">
                  {health.reachable ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400" />
                  )}
                </span>
              )}
            </div>
            <p className="text-sm text-muted mt-0.5">
              Container image repository at <code className="font-mono text-xs">{registryHost}</code>
            </p>
          </div>
        </div>
      </div>

      {/* Summary bar */}
      {!isLoading && !isError && !registryError && repos.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <div className="card p-4">
            <p className="text-label text-xs mb-1">Repositories</p>
            <p className="text-2xl font-semibold text-heading">{repos.length}</p>
          </div>
          <div className="card p-4">
            <p className="text-label text-xs mb-1">Total Images</p>
            <p className="text-2xl font-semibold text-heading">{totalTags}</p>
          </div>
          <div className="card p-4 col-span-2">
            <p className="text-label text-xs mb-1">Push Command</p>
            <div className="flex items-center gap-1 mt-1">
              <code className="text-xs font-mono text-emerald-400 truncate">
                docker push {registryHost}/&lt;image&gt;:&lt;tag&gt;
              </code>
              <CopyButton text={`docker push ${registryHost}/`} />
            </div>
          </div>
        </div>
      )}

      {/* Push instructions when empty */}
      {!isLoading && !isError && !registryError && repos.length === 0 && (
        <div className="card p-8">
          <div className="max-w-lg mx-auto text-center">
            <Package className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
            <h3 className="text-heading text-lg mb-2">No repositories yet</h3>
            <p className="text-sm text-muted mb-6">
              Push images to your registry or deploy a site to get started.
            </p>
          </div>

          <div className="max-w-xl mx-auto space-y-3">
            <h4 className="text-xs font-semibold text-heading uppercase tracking-wider flex items-center gap-2">
              <Terminal className="w-4 h-4" />
              Quick Start
            </h4>
            {[
              { step: '1', label: 'Build your image', cmd: `docker build -t ${registryHost}/my-app:latest .` },
              { step: '2', label: 'Push to registry', cmd: `docker push ${registryHost}/my-app:latest` },
              { step: '3', label: 'Or deploy a site', cmd: 'The build pipeline automatically pushes to the registry' },
            ].map(({ step, label, cmd }) => (
              <div key={step} className="flex gap-3">
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                  <span className="text-xs font-bold text-blue-400">{step}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-200">{label}</div>
                  <div className="flex items-center gap-1 mt-1">
                    <code className="block px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-xs text-emerald-400 flex-1 overflow-x-auto">
                      {step === '3' ? cmd : `$ ${cmd}`}
                    </code>
                    {step !== '3' && <CopyButton text={cmd} />}
                  </div>
                </div>
              </div>
            ))}

            <div className="mt-4 pt-4 border-t border-white/5">
              <p className="text-xs text-muted">
                {registryHost.includes(':5000')
                  ? <>For remote access, use an SSH tunnel: <code className="font-mono text-gray-400">ssh -L 5000:localhost:5000 user@server</code></>
                  : <>Registry available at <code className="font-mono text-gray-400">https://{registryHost}</code></>
                }
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="text-muted text-sm">Loading registry...</div>
      )}

      {/* Fetch error */}
      {isError && (
        <div className="card p-8 text-center">
          <Package className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-label mb-1">Registry unavailable</h3>
          <p className="text-sm text-muted">
            {(error as Error)?.message ?? 'Could not connect to the Docker registry.'}
          </p>
        </div>
      )}

      {/* API-level error */}
      {!isLoading && !isError && registryError && (
        <div className="card p-8 text-center">
          <Package className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-label mb-1">Registry error</h3>
          <p className="text-sm text-muted">{registryError}</p>
        </div>
      )}

      {/* Repository list */}
      {!isLoading && !isError && !registryError && repos.length > 0 && (
        <div className="space-y-3">
          {repos.map(repo => (
            <RepoCard key={repo.repository} repo={repo} registryHost={registryHost} />
          ))}
        </div>
      )}
    </div>
  );
}

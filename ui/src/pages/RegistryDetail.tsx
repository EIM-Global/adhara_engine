import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { TagDetail } from '../api/client';
import { useState } from 'react';
import {
  Package, ArrowLeft, Trash2, Rocket, Copy, Check, Terminal,
  ExternalLink, Tag, Layers, Clock, Cpu, AlertTriangle,
} from 'lucide-react';
import { useRegistryHost } from '../hooks/useRegistryHost';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}

function shortDigest(digest: string): string {
  if (!digest) return '—';
  // sha256:abcdef... → sha256:abcdef
  const parts = digest.split(':');
  if (parts.length === 2) return `${parts[0]}:${parts[1].slice(0, 12)}`;
  return digest.slice(0, 19);
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="p-1 rounded hover:bg-white/10 transition-colors"
      title="Copy"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-gray-500" />}
    </button>
  );
}

export default function RegistryDetail() {
  const { repo } = useParams<{ repo: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const repository = decodeURIComponent(repo || '');

  const [deleteConfirmTag, setDeleteConfirmTag] = useState<string | null>(null);
  const [deleteRepoConfirm, setDeleteRepoConfirm] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['registry-detail', repository],
    queryFn: () => api.getRegistryRepoDetail(repository),
    enabled: !!repository,
    refetchInterval: 15000,
  });

  const deleteTagMutation = useMutation({
    mutationFn: (tag: string) => api.deleteRegistryTag(repository, tag),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registry-detail', repository] });
      queryClient.invalidateQueries({ queryKey: ['registry'] });
      setDeleteConfirmTag(null);
    },
  });

  const deleteRepoMutation = useMutation({
    mutationFn: () => api.deleteRegistryRepo(repository),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['registry'] });
      navigate('/registry');
    },
  });

  const registryHost = useRegistryHost();
  const fullImageRef = `${registryHost}/${repository}`;

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="text-muted text-sm">Loading repository details...</div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="p-6">
        <div className="card p-8 text-center">
          <Package className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
          <h3 className="text-label mb-1">Repository not found</h3>
          <p className="text-sm text-muted mb-4">Could not load details for "{repository}"</p>
          <Link to="/registry" className="link text-sm">Back to Registry</Link>
        </div>
      </div>
    );
  }

  const tagDetails: TagDetail[] = data.tag_details ?? [];
  const sortedTags = [...tagDetails].sort((a, b) => {
    // Put 'latest' first, then sort by creation date descending
    if (a.tag === 'latest') return -1;
    if (b.tag === 'latest') return 1;
    if (a.created && b.created) return new Date(b.created).getTime() - new Date(a.created).getTime();
    return 0;
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <Link to="/registry" className="inline-flex items-center gap-1 text-sm text-muted hover:text-body transition-colors mb-3">
          <ArrowLeft className="w-4 h-4" />
          Back to Registry
        </Link>

        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
              <Package className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-heading text-2xl font-mono">{repository}</h1>
              <div className="flex items-center gap-2 mt-0.5">
                <code className="text-xs font-mono text-muted">{fullImageRef}</code>
                <CopyButton text={fullImageRef} />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {data.site_id ? (
              <Link
                to={`/sites/${data.site_id}`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-white/10 hover:border-white/20 transition-colors"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                View Site
              </Link>
            ) : (
              <button
                onClick={() => navigate(`/sites?create=true&source_type=docker_image&source_url=${encodeURIComponent(fullImageRef + ':latest')}&name=${encodeURIComponent(repository.replace('ae-', ''))}`)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors"
              >
                <Rocket className="w-3.5 h-3.5" />
                Deploy as Site
              </button>
            )}
            <button
              onClick={() => setDeleteRepoConfirm(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-red-500/20 text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete Repo
            </button>
          </div>
        </div>

        {/* Linked site info */}
        {data.site_id && (
          <div className="mt-3 flex items-center gap-2 text-sm">
            <span className="text-muted">Linked to site</span>
            <Link to={`/sites/${data.site_id}`} className="link inline-flex items-center gap-1">
              {data.site_name ?? data.site_slug}
              <ExternalLink className="w-3 h-3" />
            </Link>
            {data.tenant_slug && data.workspace_slug && (
              <span className="text-muted text-xs">&middot; {data.tenant_slug} / {data.workspace_slug}</span>
            )}
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="card p-4">
          <p className="text-label text-xs mb-1">Tags</p>
          <p className="text-2xl font-semibold text-heading">{data.tags.length}</p>
        </div>
        <div className="card p-4">
          <p className="text-label text-xs mb-1">Total Size</p>
          <p className="text-2xl font-semibold text-heading">
            {formatBytes(tagDetails.reduce((sum, t) => sum + t.size, 0))}
          </p>
        </div>
        <div className="card p-4 col-span-2">
          <p className="text-label text-xs mb-1">Pull Command</p>
          <div className="flex items-center gap-1 mt-1">
            <code className="text-xs font-mono text-emerald-400 truncate">
              docker pull {fullImageRef}:latest
            </code>
            <CopyButton text={`docker pull ${fullImageRef}:latest`} />
          </div>
        </div>
      </div>

      {/* Push instructions */}
      <div className="card p-4 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Terminal className="w-4 h-4 text-blue-400" />
          <h3 className="text-heading text-sm font-semibold">Push Instructions</h3>
        </div>
        <div className="space-y-2">
          {[
            { label: 'Tag your image', cmd: `docker tag <image> ${fullImageRef}:<tag>` },
            { label: 'Push to registry', cmd: `docker push ${fullImageRef}:<tag>` },
          ].map(({ label, cmd }) => (
            <div key={label} className="flex items-center gap-2">
              <span className="text-xs text-muted w-28 flex-shrink-0">{label}</span>
              <code className="flex-1 px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-xs text-emerald-400 overflow-x-auto">
                $ {cmd}
              </code>
              <CopyButton text={cmd} />
            </div>
          ))}
        </div>
      </div>

      {/* Tags table */}
      <div className="card overflow-hidden">
        <div className="p-4 border-b border-white/[0.06]">
          <h3 className="text-heading text-sm font-semibold">Image Tags</h3>
        </div>

        {sortedTags.length === 0 ? (
          <div className="p-8 text-center">
            <Tag className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-sm text-muted">No tags in this repository</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted uppercase tracking-wider">
                  <th className="px-4 py-3">Tag</th>
                  <th className="px-4 py-3">Digest</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3">Layers</th>
                  <th className="px-4 py-3">Platform</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {sortedTags.map((td) => (
                  <tr key={td.tag} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Tag className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
                        <span className="font-mono font-medium">{td.tag}</span>
                        {td.tag === 'latest' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 font-medium">
                            latest
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <code className="text-xs font-mono text-muted">{shortDigest(td.digest)}</code>
                        <CopyButton text={td.digest} />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted">{formatBytes(td.size)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-muted">
                        <Layers className="w-3 h-3" />
                        {td.layers}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {td.architecture ? (
                        <div className="flex items-center gap-1 text-muted text-xs">
                          <Cpu className="w-3 h-3" />
                          {td.architecture}
                        </div>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-muted text-xs">
                        <Clock className="w-3 h-3" />
                        {formatDate(td.created)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => navigate(`/sites?create=true&source_type=docker_image&source_url=${encodeURIComponent(fullImageRef + ':' + td.tag)}&name=${encodeURIComponent(repository.replace('ae-', '') + '-' + td.tag)}`)}
                          className="p-1.5 rounded hover:bg-blue-500/10 text-blue-400 transition-colors"
                          title="Deploy as Site"
                        >
                          <Rocket className="w-3.5 h-3.5" />
                        </button>
                        <CopyButton text={`${fullImageRef}:${td.tag}`} />
                        {deleteConfirmTag === td.tag ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => deleteTagMutation.mutate(td.tag)}
                              disabled={deleteTagMutation.isPending}
                              className="px-2 py-1 rounded text-[10px] font-medium bg-red-600 text-white hover:bg-red-500 transition-colors disabled:opacity-50"
                            >
                              {deleteTagMutation.isPending ? '...' : 'Confirm'}
                            </button>
                            <button
                              onClick={() => setDeleteConfirmTag(null)}
                              className="px-2 py-1 rounded text-[10px] font-medium border border-white/10 hover:border-white/20 transition-colors"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirmTag(td.tag)}
                            className="p-1.5 rounded hover:bg-red-500/10 text-red-400 transition-colors"
                            title="Delete tag"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete repo confirmation modal */}
      {deleteRepoConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="card p-6 max-w-md w-full mx-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <div>
                <h3 className="text-heading font-semibold">Delete Repository</h3>
                <p className="text-xs text-muted mt-0.5">This action cannot be undone</p>
              </div>
            </div>
            <p className="text-sm text-muted mb-1">
              Are you sure you want to delete <strong className="text-body font-mono">{repository}</strong> and all its tags?
            </p>
            <p className="text-xs text-muted mb-4">
              {data.tags.length} tag{data.tags.length !== 1 ? 's' : ''} will be permanently removed.
              {data.site_id && ' The linked site will not be affected but future deployments may fail.'}
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setDeleteRepoConfirm(false)}
                className="px-4 py-2 text-sm rounded-lg border border-white/10 hover:border-white/20 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteRepoMutation.mutate()}
                disabled={deleteRepoMutation.isPending}
                className="px-4 py-2 text-sm rounded-lg bg-red-600 text-white hover:bg-red-500 transition-colors disabled:opacity-50"
              >
                {deleteRepoMutation.isPending ? 'Deleting...' : `Delete ${data.tags.length} tags`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

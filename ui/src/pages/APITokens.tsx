import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { APIToken, APITokenCreateResponse } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import {
  Key,
  Plus,
  Copy,
  Check,
  AlertTriangle,
  Trash2,
} from 'lucide-react';

export default function APITokens() {
  const queryClient = useQueryClient();

  // ---- state ----------------------------------------------------------------
  const [name, setName] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [newToken, setNewToken] = useState<APITokenCreateResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState<string | null>(null);

  // ---- queries --------------------------------------------------------------
  const { data: tokens, isLoading } = useQuery({
    queryKey: ['api-tokens'],
    queryFn: api.listTokens,
  });

  // ---- mutations ------------------------------------------------------------
  const createMut = useMutation({
    mutationFn: (data: { name: string; expires_at?: string }) => api.createToken(data),
    onSuccess: (resp) => {
      setNewToken(resp);
      setName('');
      setExpiresAt('');
      queryClient.invalidateQueries({ queryKey: ['api-tokens'] });
    },
  });

  const revokeMut = useMutation({
    mutationFn: (id: string) => api.revokeToken(id),
    onSuccess: () => {
      setConfirmRevoke(null);
      queryClient.invalidateQueries({ queryKey: ['api-tokens'] });
    },
  });

  // ---- handlers -------------------------------------------------------------
  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    createMut.mutate({
      name: name.trim(),
      ...(expiresAt ? { expires_at: new Date(expiresAt).toISOString() } : {}),
    });
  }

  function handleCopy(token: string) {
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  // ---- render ---------------------------------------------------------------
  const allTokens: APIToken[] = tokens ?? [];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-heading text-2xl">API Tokens</h1>
        <p className="text-sm text-muted mt-1">
          Create tokens for CI/CD and automation
        </p>
      </div>

      {/* ---- Create Token form ---- */}
      <div className="card p-5 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Plus className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          <h2 className="text-heading text-lg">Create Token</h2>
        </div>

        <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label htmlFor="token-name" className="block text-sm text-label mb-1">
              Name
            </label>
            <input
              id="token-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. CI deploy token"
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
              required
            />
          </div>

          <div className="min-w-[180px]">
            <label htmlFor="token-expiry" className="block text-sm text-label mb-1">
              Expires (optional)
            </label>
            <input
              id="token-expiry"
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
            />
          </div>

          <button
            type="submit"
            disabled={createMut.isPending || !name.trim()}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMut.isPending ? 'Creating...' : 'Create'}
          </button>
        </form>

        {createMut.isError && (
          <p className="text-sm text-red-600 mt-2">
            {(createMut.error as Error).message}
          </p>
        )}
      </div>

      {/* ---- Newly created token alert ---- */}
      {newToken && (
        <div className="bg-yellow-50 border border-yellow-300 dark:bg-yellow-900/20 dark:border-yellow-700 rounded-lg p-4 mb-6">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-yellow-800 dark:text-yellow-300 mb-1">
                Save this token -- it won't be shown again
              </p>
              <div className="flex items-center gap-2 mt-2">
                <code className="bg-yellow-100 border border-yellow-200 dark:bg-yellow-900/30 dark:border-yellow-700 rounded px-3 py-1.5 text-sm font-mono text-yellow-900 dark:text-yellow-300 break-all flex-1">
                  {newToken.token}
                </code>
                <button
                  onClick={() => handleCopy(newToken.token)}
                  className="border rounded px-3 py-1.5 text-sm hover:bg-yellow-100 dark:hover:bg-yellow-900/30 dark:border-gray-600 flex items-center gap-1 flex-shrink-0"
                >
                  {copied ? (
                    <>
                      <Check className="w-4 h-4 text-green-600" />
                      <span className="text-green-700 dark:text-green-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                      <span className="dark:text-gray-300">Copy</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          <div className="flex justify-end mt-3">
            <button
              onClick={() => setNewToken(null)}
              className="text-xs text-yellow-700 dark:text-yellow-400 hover:underline"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* ---- Token list ---- */}
      <div className="card overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b dark:border-gray-700 bg-gray-50/80 dark:bg-gray-800/50">
          <Key className="w-4 h-4 text-muted" />
          <h2 className="text-sm text-label">Your Tokens</h2>
        </div>

        {isLoading ? (
          <div className="p-6 text-sm text-muted">Loading tokens...</div>
        ) : allTokens.length === 0 ? (
          <div className="p-8 text-center">
            <Key className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-muted">No API tokens yet. Create one above.</p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="thead">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Token</th>
                <th className="px-4 py-3 font-medium">Created</th>
                <th className="px-4 py-3 font-medium">Expires</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 w-20"></th>
              </tr>
            </thead>
            <tbody className="tbody">
              {allTokens.map((t) => {
                const isRevoked = t.revoked;
                const isExpired =
                  t.expires_at && new Date(t.expires_at).getTime() < Date.now();
                const status = isRevoked
                  ? 'revoked'
                  : isExpired
                    ? 'expired'
                    : 'active';

                return (
                  <tr key={t.id} className="trow">
                    <td className="px-4 py-3 text-heading">{t.name}</td>
                    <td className="px-4 py-3 font-mono text-xs text-muted">
                      {t.token_prefix}...
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">
                      {new Date(t.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">
                      {t.expires_at
                        ? new Date(t.expires_at).toLocaleDateString()
                        : 'Never'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={status} />
                    </td>
                    <td className="px-4 py-3">
                      {!isRevoked && (
                        <>
                          {confirmRevoke === t.id ? (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => revokeMut.mutate(t.id)}
                                disabled={revokeMut.isPending}
                                className="text-xs text-red-600 font-medium hover:underline"
                              >
                                Confirm
                              </button>
                              <span className="text-gray-300 dark:text-gray-600">|</span>
                              <button
                                onClick={() => setConfirmRevoke(null)}
                                className="text-xs text-muted hover:underline"
                              >
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setConfirmRevoke(t.id)}
                              className="text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                              title="Revoke token"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

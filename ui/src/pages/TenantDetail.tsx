import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Workspace } from '../api/client';
import { Plus, ArrowLeft } from 'lucide-react';
import clsx from 'clsx';
import MembersPanel from '../components/MembersPanel';

const TENANT_ROLES = [
  { value: 'tenant_owner', label: 'Owner' },
  { value: 'tenant_admin', label: 'Admin' },
  { value: 'tenant_member', label: 'Member' },
];

type Tab = 'workspaces' | 'members';

export default function TenantDetail() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const { data: tenant } = useQuery({ queryKey: ['tenant', tenantId], queryFn: () => api.getTenant(tenantId!) });
  const { data: workspaces, isLoading } = useQuery({
    queryKey: ['workspaces', tenantId],
    queryFn: () => api.listWorkspaces(tenantId!),
  });
  const [showCreate, setShowCreate] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('workspaces');

  return (
    <div className="p-6">
      <Link to="/tenants" className="flex items-center gap-1 text-sm text-muted hover:text-gray-700 dark:hover:text-gray-300 mb-4">
        <ArrowLeft className="w-4 h-4" /> Tenants
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-heading text-2xl">{tenant?.name ?? '...'}</h1>
          <p className="text-sm text-muted">{tenant?.slug} &middot; {tenant?.plan} &middot; {tenant?.owner_email}</p>
        </div>
        {activeTab === 'workspaces' && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" /> New Workspace
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        <button
          onClick={() => setActiveTab('workspaces')}
          className={clsx('tab', activeTab === 'workspaces' && 'active')}
        >
          Workspaces
        </button>
        <button
          onClick={() => setActiveTab('members')}
          className={clsx('tab', activeTab === 'members' && 'active')}
        >
          Members
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'workspaces' && (
        <>
          {showCreate && <CreateWorkspaceForm tenantId={tenantId!} onDone={() => setShowCreate(false)} />}

          {isLoading ? (
            <p className="text-muted">Loading...</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {workspaces?.map((ws: Workspace) => (
                <Link
                  key={ws.id}
                  to={`/workspaces/${ws.id}`}
                  className="card p-5 hover:border-blue-300 dark:hover:border-blue-600 transition-colors"
                >
                  <h3 className="text-heading">{ws.name}</h3>
                  <p className="text-xs text-faint font-mono">{ws.slug}</p>
                  {ws.adhara_api_url && (
                    <p className="text-xs text-muted mt-2 truncate">API: {ws.adhara_api_url}</p>
                  )}
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {activeTab === 'members' && (
        <MembersPanel
          resourceType="tenant"
          resourceId={tenantId!}
          availableRoles={TENANT_ROLES}
        />
      )}
    </div>
  );
}

function CreateWorkspaceForm({ tenantId, onDone }: { tenantId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [apiUrl, setApiUrl] = useState('');

  const mut = useMutation({
    mutationFn: () => api.createWorkspace(tenantId, { name, adhara_api_url: apiUrl || undefined }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['workspaces', tenantId] }); onDone(); },
  });

  return (
    <div className="card p-5 mb-6">
      <h3 className="font-semibold mb-3">Create Workspace</h3>
      <div className="grid grid-cols-2 gap-3">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Workspace name" className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200" />
        <input value={apiUrl} onChange={e => setApiUrl(e.target.value)} placeholder="Adhara API URL (optional)" className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200" />
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={() => mut.mutate()} disabled={!name} className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">Create</button>
        <button onClick={onDone} className="text-muted px-4 py-1.5 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800/30">Cancel</button>
      </div>
    </div>
  );
}

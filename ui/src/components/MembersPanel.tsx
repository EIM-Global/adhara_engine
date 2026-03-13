import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { UserPlus, Trash2 } from 'lucide-react';
import { api } from '../api/client';
import type { Membership } from '../api/client';

interface MembersPanelProps {
  resourceType: 'tenant' | 'workspace' | 'site';
  resourceId: string;
  availableRoles: { value: string; label: string }[];
}

const apiMethods = {
  tenant: {
    list: api.listTenantMembers,
    add: api.addTenantMember,
    update: api.updateTenantMember,
    remove: api.removeTenantMember,
  },
  workspace: {
    list: api.listWorkspaceMembers,
    add: api.addWorkspaceMember,
    update: api.updateWorkspaceMember,
    remove: api.removeWorkspaceMember,
  },
  site: {
    list: api.listSiteMembers,
    add: api.addSiteMember,
    update: api.updateSiteMember,
    remove: api.removeSiteMember,
  },
} as const;

export default function MembersPanel({ resourceType, resourceId, availableRoles }: MembersPanelProps) {
  const qc = useQueryClient();
  const methods = apiMethods[resourceType];
  const queryKey = ['members', resourceType, resourceId];

  const { data: members, isLoading } = useQuery({
    queryKey,
    queryFn: () => methods.list(resourceId),
  });

  const [email, setEmail] = useState('');
  const [userId, setUserId] = useState('');
  const [role, setRole] = useState(availableRoles[0]?.value ?? '');
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);

  const addMut = useMutation({
    mutationFn: () => methods.add(resourceId, { user_id: userId || email, user_email: email, role }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      setEmail('');
      setUserId('');
      setRole(availableRoles[0]?.value ?? '');
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ memberId, newRole }: { memberId: string; newRole: string }) =>
      methods.update(resourceId, memberId, { role: newRole }),
    onSuccess: () => qc.invalidateQueries({ queryKey }),
  });

  const removeMut = useMutation({
    mutationFn: (memberId: string) => methods.remove(resourceId, memberId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey });
      setConfirmRemove(null);
    },
  });

  return (
    <div>
      {/* Add Member Form */}
      <div className="card p-5 mb-4">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <UserPlus className="w-4 h-4" /> Add Member
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <input
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="Email address"
            type="email"
            className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
          />
          <input
            value={userId}
            onChange={e => setUserId(e.target.value)}
            placeholder="User ID (optional)"
            className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
          />
          <select
            value={role}
            onChange={e => setRole(e.target.value)}
            className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
          >
            {availableRoles.map(r => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
          <button
            onClick={() => addMut.mutate()}
            disabled={!email || addMut.isPending}
            className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
          >
            {addMut.isPending ? 'Adding...' : 'Add'}
          </button>
        </div>
        {addMut.isError && (
          <p className="text-red-600 text-sm mt-2">{(addMut.error as Error).message}</p>
        )}
      </div>

      {/* Members Table */}
      {isLoading ? (
        <p className="text-muted">Loading members...</p>
      ) : !members?.length ? (
        <p className="text-faint text-sm">No members yet.</p>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="thead">
              <tr>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Added</th>
                <th className="px-4 py-3 font-medium w-16"></th>
              </tr>
            </thead>
            <tbody className="tbody">
              {members.map((m: Membership) => (
                <tr key={m.id} className="trow">
                  <td className="px-4 py-3">
                    <span className="text-heading">{m.user_email}</span>
                    <p className="text-xs text-faint font-mono">{m.user_id}</p>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={m.role}
                      onChange={e => updateMut.mutate({ memberId: m.user_id, newRole: e.target.value })}
                      className="border rounded px-2 py-1 text-sm bg-white dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200"
                    >
                      {availableRoles.map(r => (
                        <option key={r.value} value={r.value}>{r.label}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-muted">
                    {new Date(m.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {confirmRemove === m.id ? (
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => removeMut.mutate(m.user_id)}
                          disabled={removeMut.isPending}
                          className="text-red-600 text-xs font-medium hover:text-red-800"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setConfirmRemove(null)}
                          className="text-gray-400 dark:text-gray-500 text-xs hover:text-gray-600 dark:hover:text-gray-300"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmRemove(m.id)}
                        className="text-gray-400 dark:text-gray-500 hover:text-red-600 transition-colors"
                        title="Remove member"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

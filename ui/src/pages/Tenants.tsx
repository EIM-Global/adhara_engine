import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import type { Tenant } from '../api/client';
import { Plus, Trash2 } from 'lucide-react';

export default function Tenants() {
  const qc = useQueryClient();
  const { data: tenants, isLoading } = useQuery({ queryKey: ['tenants'], queryFn: api.listTenants });
  const [showCreate, setShowCreate] = useState(false);

  const deleteMut = useMutation({
    mutationFn: (id: string) => api.deleteTenant(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tenants'] }),
  });

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-heading text-2xl">Tenants</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" /> New Tenant
        </button>
      </div>

      {showCreate && <CreateTenantForm onDone={() => setShowCreate(false)} />}

      {isLoading ? (
        <p className="text-muted">Loading...</p>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="thead">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Slug</th>
                <th className="px-4 py-3 font-medium">Plan</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium w-16"></th>
              </tr>
            </thead>
            <tbody className="tbody">
              {tenants?.map((t: Tenant) => (
                <tr key={t.id} className="trow">
                  <td className="px-4 py-3">
                    <Link to={`/tenants/${t.id}`} className="link">
                      {t.name}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-muted font-mono text-xs">{t.slug}</td>
                  <td className="px-4 py-3">
                    <span className="bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400 px-2 py-0.5 rounded text-xs">{t.plan}</span>
                  </td>
                  <td className="px-4 py-3 text-muted">{t.owner_email}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => { if (confirm(`Delete ${t.name}?`)) deleteMut.mutate(t.id); }}
                      className="text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
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

function CreateTenantForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [plan, setPlan] = useState('free');

  const mut = useMutation({
    mutationFn: () => api.createTenant({ name, owner_email: email, plan }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tenants'] }); onDone(); },
  });

  return (
    <div className="card p-5 mb-6">
      <h3 className="font-semibold mb-3 dark:text-white">Create Tenant</h3>
      <div className="grid grid-cols-3 gap-3">
        <input value={name} onChange={e => setName(e.target.value)} placeholder="Name" className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200" />
        <input value={email} onChange={e => setEmail(e.target.value)} placeholder="Email" className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200" />
        <select value={plan} onChange={e => setPlan(e.target.value)} className="border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200">
          <option value="free">Free</option>
          <option value="starter">Starter</option>
          <option value="pro">Pro</option>
          <option value="enterprise">Enterprise</option>
        </select>
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={() => mut.mutate()} disabled={!name || !email} className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 disabled:opacity-50">Create</button>
        <button onClick={onDone} className="text-muted px-4 py-1.5 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-700">Cancel</button>
      </div>
    </div>
  );
}

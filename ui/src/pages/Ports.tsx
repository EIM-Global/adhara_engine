import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import StatusBadge from '../components/StatusBadge';

export default function Ports() {
  const { data: ports, isLoading } = useQuery({ queryKey: ['ports'], queryFn: api.listPorts });

  return (
    <div className="p-6">
      <h1 className="text-heading text-2xl mb-6">Port Routing Table</h1>

      {isLoading ? (
        <p className="text-muted">Loading...</p>
      ) : (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="thead">
              <tr>
                <th className="px-4 py-3 font-medium">Site</th>
                <th className="px-4 py-3 font-medium">Tenant</th>
                <th className="px-4 py-3 font-medium">Workspace</th>
                <th className="px-4 py-3 font-medium">Host Port</th>
                <th className="px-4 py-3 font-medium">Container Port</th>
                <th className="px-4 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="tbody">
              {(ports as any[])?.map((p, i) => (
                <tr key={i} className="trow">
                  <td className="px-4 py-3 font-medium dark:text-white">{p.site_slug}</td>
                  <td className="px-4 py-3 text-muted">{p.tenant_slug}</td>
                  <td className="px-4 py-3 text-muted">{p.workspace_slug}</td>
                  <td className="px-4 py-3 font-mono dark:text-gray-200">{p.host_port}</td>
                  <td className="px-4 py-3 font-mono dark:text-gray-200">{p.container_port}</td>
                  <td className="px-4 py-3"><StatusBadge status={p.status} /></td>
                </tr>
              ))}
              {(!ports || (ports as any[]).length === 0) && (
                <tr><td colSpan={6} className="px-4 py-6 text-center text-faint">No port mappings</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

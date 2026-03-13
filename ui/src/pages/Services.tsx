import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ServiceInfo } from '../api/client';
import {
  Server, Database, Zap, Network, HardDrive, ScrollText, RadioTower,
  BarChart3, Shield, LayoutDashboard, Box, Container,
  ExternalLink, RotateCw, ChevronDown, ChevronUp, Play,
  Eye, EyeOff, Copy, Check, KeyRound,
} from 'lucide-react';

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  server: Server,
  database: Database,
  zap: Zap,
  network: Network,
  'hard-drive': HardDrive,
  'scroll-text': ScrollText,
  'radio-tower': RadioTower,
  'bar-chart-3': BarChart3,
  shield: Shield,
  'layout-dashboard': LayoutDashboard,
  box: Box,
  container: Container,
};

const CATEGORY_LABELS: Record<string, string> = {
  core: 'Core',
  data: 'Data Stores',
  networking: 'Networking',
  storage: 'Storage',
  observability: 'Observability',
  auth: 'Authentication',
};

function StatusDot({ status, health }: { status: string; health: string | null }) {
  const isHealthy = health === 'healthy';
  const isRunning = status === 'running';
  const isUnhealthy = health === 'unhealthy';

  let color = 'bg-gray-400';
  let label = status;

  if (isRunning && isHealthy) {
    color = 'bg-green-500';
    label = 'healthy';
  } else if (isRunning && isUnhealthy) {
    color = 'bg-red-500';
    label = 'unhealthy';
  } else if (isRunning) {
    color = 'bg-green-500';
    label = 'running';
  } else if (status === 'exited') {
    color = 'bg-gray-400';
    label = 'stopped';
  }

  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block w-2.5 h-2.5 rounded-full ${color} ${isRunning ? 'animate-pulse' : ''}`} />
      <span className={`text-xs font-medium ${isRunning ? 'text-green-700 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'}`}>
        {label}
      </span>
    </div>
  );
}

function timeSince(dateStr: string | null): string {
  if (!dateStr) return '—';
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function CredentialsBadge({ username, password }: { username: string; password: string | null }) {
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const handleCopy = async (value: string, label: string) => {
    await navigator.clipboard.writeText(value);
    setCopied(label);
    setTimeout(() => setCopied(null), 1500);
  };

  return (
    <div className="mt-3 flex items-center gap-3 bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-700 rounded-lg px-3 py-2">
      <KeyRound className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
      <div className="flex items-center gap-3 text-xs flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-amber-700 dark:text-amber-400 font-medium">User:</span>
          <code className="text-gray-800 dark:text-gray-200 font-mono">{username}</code>
          <button onClick={() => handleCopy(username, 'user')} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300" title="Copy username">
            {copied === 'user' ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
          </button>
        </div>
        {password && (
          <div className="flex items-center gap-1.5">
            <span className="text-amber-700 dark:text-amber-400 font-medium">Pass:</span>
            <code className="text-gray-800 dark:text-gray-200 font-mono">
              {showPassword ? password : '\u2022'.repeat(Math.min(password.length, 12))}
            </code>
            <button onClick={() => setShowPassword(!showPassword)} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300" title={showPassword ? 'Hide' : 'Show'}>
              {showPassword ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
            </button>
            <button onClick={() => handleCopy(password, 'pass')} className="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300" title="Copy password">
              {copied === 'pass' ? <Check className="w-3 h-3 text-green-500" /> : <Copy className="w-3 h-3" />}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ServiceCard({ service }: { service: ServiceInfo }) {
  const qc = useQueryClient();
  const [showLogs, setShowLogs] = useState(false);
  const Icon = ICON_MAP[service.icon] || Box;

  const restartMut = useMutation({
    mutationFn: () => api.restartService(service.name),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['services'] }),
  });

  const { data: logsData, isFetching: logsFetching, refetch: fetchLogs } = useQuery({
    queryKey: ['service-logs', service.name],
    queryFn: () => api.getServiceLogs(service.name, 100),
    enabled: false,
  });

  const handleToggleLogs = () => {
    if (!showLogs) {
      fetchLogs();
    }
    setShowLogs(!showLogs);
  };

  const portEntries = Object.entries(service.ports || {});

  return (
    <div className="card transition-shadow">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3">
            <div className="icon-box">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-heading">{service.display_name}</h3>
              <p className="text-xs text-muted mt-0.5">{service.description}</p>
            </div>
          </div>
          <StatusDot status={service.status} health={service.health} />
        </div>

        {/* Details row */}
        <div className="mt-3 flex items-center gap-4 text-xs text-muted">
          <span className="font-mono truncate max-w-[200px]" title={service.image}>{service.image}</span>
          {portEntries.length > 0 && (
            <span className="font-mono">
              {portEntries.map(([, host]) => host).join(', ')}
            </span>
          )}
          <span>Up {timeSince(service.started_at)}</span>
        </div>

        {/* Credentials */}
        {service.credentials && (
          <CredentialsBadge username={service.credentials.username} password={service.credentials.password} />
        )}

        {/* Actions row */}
        <div className="mt-3 flex items-center gap-2">
          {service.management_url && (
            <a
              href={service.management_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 border border-blue-200 dark:border-blue-800 rounded px-2.5 py-1.5 hover:bg-blue-50 dark:hover:bg-blue-900/30 active:bg-blue-100 transition-colors"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {service.management_label || 'Open'}
            </a>
          )}
          <button
            onClick={handleToggleLogs}
            className="inline-flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border dark:border-gray-600 rounded px-2.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 active:bg-gray-200 dark:active:bg-gray-600 transition-colors"
          >
            {showLogs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            Logs
          </button>
          <button
            onClick={() => restartMut.mutate()}
            disabled={restartMut.isPending || service.status !== 'running'}
            className="inline-flex items-center gap-1 text-xs text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 border dark:border-gray-600 rounded px-2.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-700 active:bg-gray-200 dark:active:bg-gray-600 transition-colors disabled:opacity-40"
          >
            <RotateCw className={`w-3.5 h-3.5 ${restartMut.isPending ? 'animate-spin' : ''}`} />
            {restartMut.isPending ? 'Restarting...' : 'Restart'}
          </button>
        </div>
      </div>

      {/* Logs panel */}
      {showLogs && (
        <div className="border-t dark:border-gray-700">
          <div className="flex items-center justify-between px-4 py-2 bg-gray-50/80 dark:bg-gray-800/50">
            <span className="text-xs font-medium text-muted">Container Logs</span>
            <button
              onClick={() => fetchLogs()}
              disabled={logsFetching}
              className="inline-flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            >
              <Play className="w-3 h-3" /> {logsFetching ? 'Loading...' : 'Refresh'}
            </button>
          </div>
          <div className="bg-gray-900 text-green-400 p-3 font-mono text-xs overflow-auto max-h-[300px]">
            {logsData?.lines?.map((line, i) => (
              <div key={i} className="leading-5 whitespace-pre">{line}</div>
            )) ?? (
              <p className="text-gray-500">Loading logs...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Services() {
  const { data, isLoading } = useQuery({
    queryKey: ['services'],
    queryFn: api.listServices,
    refetchInterval: 10000,
  });

  const services = data?.services ?? [];

  // Group by category
  const grouped: Record<string, ServiceInfo[]> = {};
  for (const s of services) {
    if (!grouped[s.category]) grouped[s.category] = [];
    grouped[s.category].push(s);
  }

  const totalRunning = services.filter(s => s.status === 'running').length;
  const totalHealthy = services.filter(s => s.health === 'healthy').length;

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-heading text-2xl">Services</h1>
          <p className="text-sm text-muted mt-1">
            {totalRunning}/{services.length} running
            {totalHealthy > 0 && ` \u00b7 ${totalHealthy} healthy`}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-muted text-sm">Loading services...</div>
      ) : (
        Object.entries(grouped).map(([category, svcs]) => (
          <div key={category} className="mb-8">
            <h2 className="section-label mb-3">
              {CATEGORY_LABELS[category] || category}
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {svcs.map(s => (
                <ServiceCard key={s.name} service={s} />
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from 'react-oidc-context';
import { useTheme } from './ThemeProvider';
import { OIDC_ENABLED, useTokenAuth } from '../auth/AuthProvider';
import { LayoutDashboard, Building2, Globe, Server, Activity, Boxes, ExternalLink, ChevronRight, Layers, LogOut, User, Key, Settings, Sun, Moon, Package } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../api/client';
import type { SiteSummary } from '../api/client';

const NAV = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/sites', label: 'Sites', icon: Layers },
  { to: '/services', label: 'Services', icon: Boxes },
  { to: '/registry', label: 'Registry', icon: Package },
  { to: '/tenants', label: 'Tenants', icon: Building2 },
  { to: '/ports', label: 'Ports', icon: Globe },
  { to: '/tokens', label: 'API Tokens', icon: Key },
  { to: '/settings', label: 'Settings', icon: Settings },
];

function SiteStatusDot({ status }: { status: string }) {
  const isRunning = status === 'running';
  const isError = status === 'error';
  const isDeploying = status === 'deploying' || status === 'building';

  return (
    <span
      className={clsx(
        'inline-block w-2 h-2 rounded-full flex-shrink-0',
        isRunning && 'bg-green-400',
        isError && 'bg-red-400',
        isDeploying && 'bg-yellow-400 animate-pulse',
        !isRunning && !isError && !isDeploying && 'bg-gray-500',
      )}
    />
  );
}

function siteUrl(site: SiteSummary): string {
  return `http://${site.slug}.${site.workspace_slug}.${site.tenant_slug}.localhost`;
}

function TenantGroup({ tenantSlug, sites }: { tenantSlug: string; sites: SiteSummary[] }) {
  const [open, setOpen] = useState(false);
  const runningCount = sites.filter(s => s.status === 'running').length;

  return (
    <div className="mb-0.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-3 py-1 text-left rounded-md hover:bg-gray-800/50 transition-colors group"
      >
        <ChevronRight
          className={clsx(
            'w-3 h-3 text-gray-600 transition-transform',
            open && 'rotate-90',
          )}
        />
        <span className="text-[11px] text-gray-500 group-hover:text-gray-300 truncate flex-1" title={tenantSlug}>
          {tenantSlug}
        </span>
        <span className="text-[10px] text-gray-600">
          {runningCount}/{sites.length}
        </span>
      </button>
      {open && (
        <div className="ml-2">
          {sites.map(site => (
            <div
              key={site.id}
              className="flex items-center gap-2 px-3 py-1 rounded-md group hover:bg-gray-800/50 transition-colors"
            >
              <SiteStatusDot status={site.status} />
              <Link
                to={`/sites/${site.id}`}
                className="flex-1 text-xs text-gray-400 group-hover:text-white truncate transition-colors"
                title={site.name}
              >
                {site.name}
              </Link>
              {site.status === 'running' && (
                <a
                  href={siteUrl(site)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-blue-400 transition-opacity"
                  title={`Open ${siteUrl(site)}`}
                  onClick={e => e.stopPropagation()}
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SidebarSites() {
  const { data: sites } = useQuery({
    queryKey: ['all-sites'],
    queryFn: api.listAllSites,
    refetchInterval: 10000,
  });

  if (!sites || sites.length === 0) return null;

  // Group by tenant
  const grouped: Record<string, SiteSummary[]> = {};
  for (const s of sites) {
    const key = s.tenant_slug;
    if (!grouped[key]) grouped[key] = [];
    grouped[key].push(s);
  }

  return (
    <div className="pb-2">
      <div className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-3 mb-1">
        Sites
      </div>
      {Object.entries(grouped).map(([tenantSlug, tenantSites]) => (
        <TenantGroup key={tenantSlug} tenantSlug={tenantSlug} sites={tenantSites} />
      ))}
    </div>
  );
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-500 rounded-md
                 hover:bg-gray-800 hover:text-gray-300 transition-colors"
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {theme === 'dark' ? <Sun className="w-3 h-3" /> : <Moon className="w-3 h-3" />}
      {theme === 'dark' ? 'Light mode' : 'Dark mode'}
    </button>
  );
}

function OidcSidebarUser() {
  const auth = useAuth();
  const name = auth.user?.profile?.name || auth.user?.profile?.email || 'User';
  const email = auth.user?.profile?.email;

  return (
    <div className="p-3 border-t border-gray-800">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/20">
          <User className="w-3.5 h-3.5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-gray-300 truncate">{name}</div>
          {email && <div className="text-[10px] text-gray-500 truncate">{email}</div>}
        </div>
      </div>
      <ThemeToggle />
      <button
        onClick={() => auth.signoutRedirect()}
        className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-500 rounded-md
                   hover:bg-gray-800 hover:text-gray-300 transition-colors mt-1"
      >
        <LogOut className="w-3 h-3" />
        Sign out
      </button>
      <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-600">
        <Activity className="w-2.5 h-2.5" />
        v0.1.0
      </div>
    </div>
  );
}

function TokenSidebarUser() {
  const { logout } = useTokenAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="p-3 border-t border-gray-800">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-lg shadow-blue-500/20">
          <Key className="w-3.5 h-3.5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-gray-300 truncate">Token Auth</div>
          <div className="text-[10px] text-gray-500 truncate">API token session</div>
        </div>
      </div>
      <ThemeToggle />
      <button
        onClick={handleLogout}
        className="flex items-center gap-2 w-full px-2 py-1.5 text-xs text-gray-500 rounded-md
                   hover:bg-gray-800 hover:text-gray-300 transition-colors mt-1"
      >
        <LogOut className="w-3 h-3" />
        Sign out
      </button>
      <div className="flex items-center gap-2 mt-2 text-[10px] text-gray-600">
        <Activity className="w-2.5 h-2.5" />
        v0.1.0
      </div>
    </div>
  );
}

function SidebarUser() {
  if (OIDC_ENABLED) {
    return <OidcSidebarUser />;
  }
  return <TokenSidebarUser />;
}

export default function Layout() {
  const { pathname } = useLocation();

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-950 flex transition-colors duration-200">
      {/* Sidebar — always dark */}
      <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col border-r border-gray-800">
        <div className="p-4 border-b border-gray-800">
          <Link to="/dashboard" className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Server className="w-4 h-4 text-white" />
            </div>
            <span className="text-white font-semibold text-lg">Adhara Engine</span>
          </Link>
        </div>
        <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
          {NAV.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150',
                (to === '/' ? pathname === '/' : pathname.startsWith(to))
                  ? 'bg-gradient-to-r from-blue-600/20 to-indigo-600/10 text-white shadow-sm'
                  : 'hover:bg-gray-800/50 hover:text-white',
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          ))}

          {/* Divider */}
          <div className="border-t border-gray-800 my-2" />

          {/* Sites section */}
          <SidebarSites />
        </nav>
        <SidebarUser />
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

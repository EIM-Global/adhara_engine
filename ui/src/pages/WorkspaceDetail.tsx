import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Site, RegistryRepo } from '../api/client';
import { Plus, ArrowLeft, Rocket, Terminal, GitBranch, Container, Package, Globe } from 'lucide-react';
import clsx from 'clsx';
import StatusBadge from '../components/StatusBadge';
import MembersPanel from '../components/MembersPanel';
import { useRegistryHost } from '../hooks/useRegistryHost';

const WORKSPACE_ROLES = [
  { value: 'workspace_admin', label: 'Admin' },
  { value: 'workspace_deployer', label: 'Deployer' },
  { value: 'workspace_viewer', label: 'Viewer' },
];

type Tab = 'sites' | 'members';

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="bg-gray-900 text-green-400 font-mono text-xs rounded p-3 overflow-x-auto whitespace-pre">
      {children}
    </pre>
  );
}

// ── Tabbed Deploy Guide ─────────────────────────────────────────

type GuideTab = 'git' | 'registry' | 'local';

function DeployGuide({ tenantSlug, workspaceSlug }: { tenantSlug: string; workspaceSlug: string }) {
  const [tab, setTab] = useState<GuideTab>('git');
  const slugPath = `${tenantSlug}/${workspaceSlug}`;
  const registryHost = useRegistryHost();

  const tabs: { id: GuideTab; label: string; icon: typeof GitBranch }[] = [
    { id: 'git', label: 'From GitHub / GitLab', icon: GitBranch },
    { id: 'registry', label: 'From Registry', icon: Package },
    { id: 'local', label: 'Local Build & Push', icon: Terminal },
  ];

  return (
    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border border-blue-200 dark:border-blue-800/50 rounded-lg p-6 mb-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="bg-blue-600 rounded-lg p-2">
          <Rocket className="w-5 h-5 text-white" />
        </div>
        <div>
          <h3 className="text-heading">Deploy Your First Site</h3>
          <p className="text-sm text-muted">Choose how you want to deploy</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-white/50 dark:bg-black/20 rounded-lg p-1 mb-5">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={clsx(
              'flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium transition-colors',
              tab === t.id
                ? 'bg-white dark:bg-gray-800 text-heading shadow-sm'
                : 'text-muted hover:text-body'
            )}
          >
            <t.icon className="w-3.5 h-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Git tab */}
      {tab === 'git' && (
        <div className="space-y-4">
          <p className="text-sm text-muted">Connect a GitHub or GitLab repository. We'll clone, build, and deploy it automatically — and redeploy on every push.</p>
          <Step n={1} title='Click "+ New Site" above and select "Git Repository"' />
          <Step n={2} title="Enter your repo URL and branch">
            <CodeBlock>{`https://github.com/your-org/your-app.git`}</CodeBlock>
            <p className="text-xs text-muted mt-1">For private repos, you'll add a deploy token or PAT in the site's Git settings after creation.</p>
          </Step>
          <Step n={3} title="Deploy and configure auto-deploy">
            <p className="text-xs text-muted">After creating the site, set up a webhook in GitHub/GitLab to auto-deploy on push. The webhook URL and secret are shown in the site's Git tab.</p>
          </Step>
        </div>
      )}

      {/* Registry tab */}
      {tab === 'registry' && (
        <div className="space-y-4">
          <p className="text-sm text-muted">Deploy an image that's already in the local registry or an external registry like Docker Hub, GHCR, or GCR.</p>
          <Step n={1} title='Click "+ New Site" and select "Registry Image"'>
            <p className="text-xs text-muted">Pick from your local registry or enter an external image URL.</p>
          </Step>
          <Step n={2} title="Set the container port and create">
            <CodeBlock>{`# Or use the CLI:
adhara-engine site create \\
  --workspace ${slugPath} \\
  --name "My App" \\
  --source docker_registry \\
  --image "${registryHost}/my-app:latest" \\
  --port 3000`}</CodeBlock>
          </Step>
          <Step n={3} title="Deploy">
            <CodeBlock>{`adhara-engine site deploy ${slugPath}/my-app`}</CodeBlock>
          </Step>
        </div>
      )}

      {/* Local build tab */}
      {tab === 'local' && (
        <div className="space-y-4">
          <p className="text-sm text-muted">Build a Docker image on your machine and push it to the Adhara registry, then deploy it as a site.</p>
          <Step n={1} title="Build and push your image">
            <CodeBlock>{`docker build -t ${registryHost}/my-app:latest .
docker push ${registryHost}/my-app:latest`}</CodeBlock>
          </Step>
          <Step n={2} title="Create the site">
            <CodeBlock>{`adhara-engine site create \\
  --workspace ${slugPath} \\
  --name "My App" \\
  --source docker_image \\
  --image "${registryHost}/my-app:latest" \\
  --port 3000`}</CodeBlock>
          </Step>
          <Step n={3} title="Deploy it">
            <CodeBlock>{`adhara-engine site deploy ${slugPath}/my-app`}</CodeBlock>
          </Step>
          <Step n={4} title="Push updates">
            <p className="text-xs text-muted">To update a running site, push a new image tag and redeploy:</p>
            <CodeBlock>{`docker build -t ${registryHost}/my-app:v2 .
docker push ${registryHost}/my-app:v2
adhara-engine site deploy ${slugPath}/my-app`}</CodeBlock>
          </Step>
        </div>
      )}
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400 text-xs font-bold shrink-0 mt-0.5">
        {n}
      </div>
      <div className="flex-1">
        <p className="text-sm text-label mb-1">{title}</p>
        {children}
      </div>
    </div>
  );
}

// ── Main Component ──────────────────────────────────────────────

export default function WorkspaceDetail() {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { data: workspace } = useQuery({
    queryKey: ['workspace', workspaceId],
    queryFn: () => api.getWorkspace(workspaceId!),
  });
  const { data: tenant } = useQuery({
    queryKey: ['tenant', workspace?.tenant_id],
    queryFn: () => api.getTenant(workspace!.tenant_id),
    enabled: !!workspace?.tenant_id,
  });
  const { data: sites, isLoading } = useQuery({
    queryKey: ['sites', workspaceId],
    queryFn: () => api.listSites(workspaceId!),
  });
  const [showCreate, setShowCreate] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('sites');

  const tenantSlug = tenant?.slug ?? 'my-tenant';
  const workspaceSlug = workspace?.slug ?? 'my-workspace';
  const hasSites = (sites?.length ?? 0) > 0;

  return (
    <div className="p-6">
      <Link to={`/tenants/${workspace?.tenant_id}`} className="flex items-center gap-1 text-sm text-muted hover:text-gray-700 dark:hover:text-gray-300 mb-4">
        <ArrowLeft className="w-4 h-4" /> Back
      </Link>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-heading text-2xl">{workspace?.name ?? '...'}</h1>
          <p className="text-sm text-muted">{workspace?.slug}</p>
          {workspace?.adhara_api_url && (
            <p className="text-xs text-faint mt-1">Adhara API: {workspace.adhara_api_url}</p>
          )}
        </div>
        {activeTab === 'sites' && (
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm hover:bg-blue-700 active:bg-blue-800"
          >
            <Plus className="w-4 h-4" /> New Site
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tab-bar">
        <button
          onClick={() => setActiveTab('sites')}
          className={clsx('tab', activeTab === 'sites' && 'active')}
        >
          Sites
        </button>
        <button
          onClick={() => setActiveTab('members')}
          className={clsx('tab', activeTab === 'members' && 'active')}
        >
          Members
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'sites' && (
        <>
          {showCreate && <CreateSiteForm workspaceId={workspaceId!} onDone={() => setShowCreate(false)} />}

          {/* Only show the full deploy guide when workspace has no sites */}
          {!hasSites && !showCreate && (
            <DeployGuide tenantSlug={tenantSlug} workspaceSlug={workspaceSlug} />
          )}

          {isLoading ? (
            <p className="text-muted">Loading...</p>
          ) : (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="thead">
                  <tr>
                    <th className="px-4 py-3 font-medium">Site</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                    <th className="px-4 py-3 font-medium">Port</th>
                  </tr>
                </thead>
                <tbody className="tbody">
                  {sites?.map((s: Site) => (
                    <tr key={s.id} className="trow">
                      <td className="px-4 py-3">
                        <Link to={`/sites/${s.id}`} className="link">
                          {s.name}
                        </Link>
                        <p className="text-xs text-faint font-mono">{s.slug}</p>
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                      <td className="px-4 py-3 text-muted">{s.source_type}</td>
                      <td className="px-4 py-3 font-mono text-muted">{s.host_port ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {activeTab === 'members' && (
        <MembersPanel
          resourceType="workspace"
          resourceId={workspaceId!}
          availableRoles={WORKSPACE_ROLES}
        />
      )}
    </div>
  );
}

/** Auto-detect git provider from clone URL */
function detectGitProvider(url: string): string | undefined {
  if (/github\.com/i.test(url)) return 'github';
  if (/gitlab\.com/i.test(url)) return 'gitlab';
  if (/bitbucket\.org/i.test(url)) return 'bitbucket';
  if (/dev\.azure\.com|visualstudio\.com/i.test(url)) return 'azure_devops';
  return undefined;
}

const INPUT_CLS = 'border rounded px-3 py-2 text-sm dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200';
const LABEL_CLS = 'block text-xs text-label mb-1';

// ── Source type cards for Create Site ────────────────────────────

const SOURCE_OPTIONS = [
  {
    value: 'git_repo',
    label: 'Git Repository',
    desc: 'Clone from GitHub, GitLab, or Bitbucket',
    icon: GitBranch,
  },
  {
    value: 'docker_registry',
    label: 'Registry Image',
    desc: 'Deploy from the local or an external registry',
    icon: Package,
  },
  {
    value: 'docker_image',
    label: 'Docker Image',
    desc: 'Pull a public image (Docker Hub, GHCR, etc.)',
    icon: Container,
  },
] as const;

function CreateSiteForm({ workspaceId, onDone }: { workspaceId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState('');
  const [sourceType, setSourceType] = useState('git_repo');
  const [sourceUrl, setSourceUrl] = useState('');
  const [port, setPort] = useState('3000');
  const [gitBranch, setGitBranch] = useState('main');
  const [registryMode, setRegistryMode] = useState<'local' | 'remote'>('local');
  const [selectedRegistryImage, setSelectedRegistryImage] = useState('');
  const registryHost = useRegistryHost();

  const { data: registryData } = useQuery({
    queryKey: ['registry'],
    queryFn: api.listRegistry,
    enabled: sourceType === 'docker_registry',
  });

  const registryOptions: { value: string; label: string; repo: RegistryRepo }[] = [];
  if (registryData?.repositories) {
    for (const repo of registryData.repositories) {
      for (const tag of repo.tags) {
        const imageRef = `${registryHost}/${repo.repository}:${tag}`;
        const label = `${repo.repository}:${tag}${repo.site_name ? ` (${repo.site_name})` : ''}`;
        registryOptions.push({ value: imageRef, label, repo });
      }
      if (repo.tags.length === 0) {
        registryOptions.push({
          value: `${registryHost}/${repo.repository}:latest`,
          label: `${repo.repository} (no tags)`,
          repo,
        });
      }
    }
  }

  const effectiveSourceUrl = (() => {
    if (sourceType === 'docker_registry') {
      return registryMode === 'local' ? selectedRegistryImage : sourceUrl;
    }
    return sourceUrl;
  })();

  const gitProvider = sourceType === 'git_repo' ? detectGitProvider(sourceUrl) : undefined;

  const mut = useMutation({
    mutationFn: () =>
      api.createSite(workspaceId, {
        name,
        source_type: sourceType,
        source_url: effectiveSourceUrl || undefined,
        container_port: parseInt(port),
        deploy_target: 'local',
        ...(sourceType === 'git_repo' && {
          git_provider: gitProvider,
          git_branch: gitBranch || 'main',
        }),
      } as Partial<Site>),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sites', workspaceId] }); onDone(); },
  });

  const canCreate = name && (
    sourceType === 'git_repo' ? !!sourceUrl :
    sourceType === 'docker_image' ? !!sourceUrl :
    sourceType === 'docker_registry' ? (registryMode === 'local' ? !!selectedRegistryImage : !!sourceUrl) :
    true
  );

  return (
    <div className="card p-5 mb-6">
      <h3 className="text-heading font-semibold mb-4">Create Site</h3>

      {/* Site name */}
      <div className="mb-4">
        <label className={LABEL_CLS}>Site name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="My App" className={`${INPUT_CLS} w-full max-w-sm`} />
      </div>

      {/* Source type cards */}
      <div className="mb-4">
        <label className={LABEL_CLS}>How do you want to deploy?</label>
        <div className="grid grid-cols-3 gap-3 mt-1">
          {SOURCE_OPTIONS.map(opt => (
            <button
              key={opt.value}
              type="button"
              onClick={() => { setSourceType(opt.value); setSourceUrl(''); setSelectedRegistryImage(''); }}
              className={clsx(
                'p-4 rounded-lg border-2 text-left transition-all',
                sourceType === opt.value
                  ? 'border-blue-500 bg-blue-600/10 dark:bg-blue-500/15 ring-2 ring-blue-500/20'
                  : 'border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800/50 hover:border-gray-300 dark:hover:border-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
              )}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <opt.icon className={clsx('w-4 h-4', sourceType === opt.value ? 'text-blue-500 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400')} />
                <span className={clsx('text-sm font-semibold', sourceType === opt.value ? 'text-blue-700 dark:text-blue-300' : 'text-gray-800 dark:text-gray-200')}>{opt.label}</span>
              </div>
              <p className="text-[11px] text-gray-500 dark:text-gray-400 leading-tight">{opt.desc}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Source-type-specific fields */}
      {sourceType === 'git_repo' && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-2 text-xs text-muted">
            <GitBranch className="w-3.5 h-3.5" />
            <span>Clone from a Git repository</span>
            {gitProvider && (
              <span className="ml-auto px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-xs font-medium capitalize">
                {gitProvider.replace('_', ' ')}
              </span>
            )}
          </div>
          <div>
            <label className={LABEL_CLS}>Repository URL</label>
            <input
              value={sourceUrl}
              onChange={e => setSourceUrl(e.target.value)}
              placeholder="https://github.com/org/repo.git"
              className={`${INPUT_CLS} w-full font-mono`}
            />
            <p className="text-xs text-faint mt-1">
              HTTPS or SSH URL. For private repos, add a deploy token after creation in the site's Git tab.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Branch</label>
              <input
                value={gitBranch}
                onChange={e => setGitBranch(e.target.value)}
                placeholder="main"
                className={`${INPUT_CLS} w-full font-mono`}
              />
            </div>
            <div>
              <label className={LABEL_CLS}>Container port</label>
              <input value={port} onChange={e => setPort(e.target.value)} placeholder="3000" className={`${INPUT_CLS} w-full font-mono`} />
            </div>
          </div>
        </div>
      )}

      {sourceType === 'docker_image' && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Container className="w-3.5 h-3.5" />
            <span>Pull a public or private Docker image</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={LABEL_CLS}>Image</label>
              <input
                value={sourceUrl}
                onChange={e => setSourceUrl(e.target.value)}
                placeholder="nginx:latest"
                className={`${INPUT_CLS} w-full font-mono`}
              />
              <p className="text-xs text-faint mt-1">
                Docker Hub (nginx:latest), GHCR (ghcr.io/org/img), or any registry URL.
              </p>
            </div>
            <div>
              <label className={LABEL_CLS}>Container port</label>
              <input value={port} onChange={e => setPort(e.target.value)} placeholder="3000" className={`${INPUT_CLS} w-full font-mono`} />
            </div>
          </div>
        </div>
      )}

      {sourceType === 'docker_registry' && (
        <div className="space-y-3 mb-4">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Package className="w-3.5 h-3.5" />
            <span>Select an image from a Docker registry</span>
          </div>

          <div className="flex gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-0.5 w-fit">
            <button
              type="button"
              onClick={() => { setRegistryMode('local'); setSourceUrl(''); }}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                registryMode === 'local'
                  ? 'bg-white dark:bg-gray-700 text-heading shadow-sm'
                  : 'text-muted hover:text-body'
              )}
            >
              Local Registry
            </button>
            <button
              type="button"
              onClick={() => { setRegistryMode('remote'); setSelectedRegistryImage(''); }}
              className={clsx(
                'px-3 py-1 rounded-md text-xs font-medium transition-colors',
                registryMode === 'remote'
                  ? 'bg-white dark:bg-gray-700 text-heading shadow-sm'
                  : 'text-muted hover:text-body'
              )}
            >
              <span className="flex items-center gap-1"><Globe className="w-3 h-3" /> Remote / Docker Hub</span>
            </button>
          </div>

          {registryMode === 'local' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={LABEL_CLS}>Registry image</label>
                {registryOptions.length > 0 ? (
                  <select
                    value={selectedRegistryImage}
                    onChange={e => setSelectedRegistryImage(e.target.value)}
                    className={`${INPUT_CLS} w-full`}
                  >
                    <option value="">Select an image...</option>
                    {registryOptions.map(opt => (
                      <option key={opt.value} value={opt.value}>{opt.label}</option>
                    ))}
                  </select>
                ) : (
                  <div className="text-xs text-muted italic py-2">
                    {registryData?.error
                      ? `Registry unavailable: ${registryData.error}`
                      : registryData
                        ? 'No images in local registry. Push an image first.'
                        : 'Loading registry...'}
                  </div>
                )}
              </div>
              <div>
                <label className={LABEL_CLS}>Container port</label>
                <input value={port} onChange={e => setPort(e.target.value)} placeholder="3000" className={`${INPUT_CLS} w-full font-mono`} />
              </div>
            </div>
          )}

          {registryMode === 'remote' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={LABEL_CLS}>Image URL</label>
                <input
                  value={sourceUrl}
                  onChange={e => setSourceUrl(e.target.value)}
                  placeholder="docker.io/library/nginx:latest"
                  className={`${INPUT_CLS} w-full font-mono`}
                />
                <p className="text-xs text-faint mt-1">
                  Docker Hub, GHCR, ECR, GCR, or any registry with public access.
                </p>
              </div>
              <div>
                <label className={LABEL_CLS}>Container port</label>
                <input value={port} onChange={e => setPort(e.target.value)} placeholder="3000" className={`${INPUT_CLS} w-full font-mono`} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {mut.isError && (
        <p className="text-sm text-red-600 dark:text-red-400 mb-3">
          {(mut.error as Error)?.message ?? 'Failed to create site'}
        </p>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1">
        <button
          onClick={() => mut.mutate()}
          disabled={!canCreate || mut.isPending}
          className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50"
        >
          {mut.isPending ? 'Creating...' : 'Create'}
        </button>
        <button onClick={onDone} className="text-muted px-4 py-1.5 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800/30 active:bg-gray-200">
          Cancel
        </button>
      </div>
    </div>
  );
}

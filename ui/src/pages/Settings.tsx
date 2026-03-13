import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { DriverInfo } from '../api/client';
import {
  Settings2, Hammer, Shield, Star, ChevronDown, ChevronRight,
  CheckCircle2, XCircle, AlertTriangle, Terminal, Copy, Check,
} from 'lucide-react';

export default function Settings() {
  const { data: buildDrivers, isLoading: buildLoading } = useQuery({
    queryKey: ['build-drivers'],
    queryFn: api.listBuildDrivers,
  });

  const { data: scanDrivers, isLoading: scanLoading } = useQuery({
    queryKey: ['scan-drivers'],
    queryFn: api.listScanDrivers,
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-heading text-2xl">Platform Settings</h1>
        <p className="text-sm text-muted mt-1">
          Available drivers and platform configuration
        </p>
      </div>

      {/* ---- Build Drivers ---- */}
      <div className="card p-5 mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Hammer className="w-5 h-5 text-blue-600 dark:text-blue-400" />
          <h2 className="text-heading text-lg">Build Drivers</h2>
        </div>

        {buildLoading ? (
          <p className="text-sm text-muted">Loading build drivers...</p>
        ) : !buildDrivers || buildDrivers.length === 0 ? (
          <div className="text-center py-6">
            <Settings2 className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-muted">No build drivers configured.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {buildDrivers.map((driver) => (
              <DriverCard key={driver.name} driver={driver} kind="build" />
            ))}
          </div>
        )}
      </div>

      {/* ---- Scan Drivers ---- */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          <h2 className="text-heading text-lg">Scan Drivers</h2>
        </div>

        {scanLoading ? (
          <p className="text-sm text-muted">Loading scan drivers...</p>
        ) : !scanDrivers || scanDrivers.length === 0 ? (
          <div className="text-center py-6">
            <Settings2 className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-2" />
            <p className="text-sm text-muted">No scan drivers configured.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {scanDrivers.map((driver) => (
              <DriverCard key={driver.name} driver={driver} kind="scan" />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Status helpers ──────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  if (status === 'ready') {
    return (
      <span className="inline-flex items-center gap-1 bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 text-xs font-medium px-2 py-0.5 rounded-full">
        <CheckCircle2 className="w-3 h-3" />
        Ready
      </span>
    );
  }
  if (status === 'not_configured') {
    return (
      <span className="inline-flex items-center gap-1 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-xs font-medium px-2 py-0.5 rounded-full">
        <AlertTriangle className="w-3 h-3" />
        Not Configured
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 text-xs font-medium px-2 py-0.5 rounded-full">
      <XCircle className="w-3 h-3" />
      Unavailable
    </span>
  );
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

// ── DriverCard ──────────────────────────────────────────────────

function DriverCard({ driver, kind }: { driver: DriverInfo; kind: 'build' | 'scan' }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card overflow-hidden">
      {/* Clickable header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center gap-3 text-left hover:bg-white/[0.02] transition-colors"
      >
        <div className="icon-box flex-shrink-0">
          {kind === 'build' ? <Hammer className="w-5 h-5" /> : <Shield className="w-5 h-5" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-heading truncate">{driver.name}</p>
            {driver.is_default && (
              <span className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 text-xs font-medium px-2 py-0.5 rounded-full">
                <Star className="w-3 h-3" />
                Default
              </span>
            )}
            <StatusBadge status={driver.status} />
          </div>
          <p className="text-xs text-muted mt-0.5 line-clamp-1">{driver.description}</p>
        </div>
        <div className="flex-shrink-0 text-gray-400">
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </button>

      {/* Expanded detail panel */}
      {expanded && (
        <div className="border-t border-white/[0.06] p-4 bg-white/[0.01] space-y-4">

          {/* Ready state — show usage info */}
          {driver.status === 'ready' && (
            <>
              <div className="flex items-start gap-2 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                <div className="text-xs text-emerald-300">
                  {driver.is_default
                    ? 'This is the default build driver. All new sites will use it automatically unless overridden.'
                    : `This driver is ready to use. Select "${driver.name}" as the build driver when creating or editing a site.`}
                </div>
              </div>

              {kind === 'build' && (
                <div>
                  <h4 className="text-xs font-semibold text-heading uppercase tracking-wider mb-2">
                    How It Works
                  </h4>
                  <ol className="text-xs text-muted space-y-1 list-decimal list-inside">
                    {driver.name === 'local_docker' && (
                      <>
                        <li>Your source code is cloned and a <code className="font-mono bg-black/30 px-1 rounded">Dockerfile</code> is built locally</li>
                        <li>The image is tagged as <code className="font-mono bg-black/30 px-1 rounded">ae-{'<site>'}:{'<sha>'}</code> and pushed to the local registry</li>
                        <li>A container is started from the image and routed via Traefik</li>
                      </>
                    )}
                    {driver.name === 'local_buildkit' && (
                      <>
                        <li>Uses Docker BuildKit for faster builds with advanced layer caching</li>
                        <li>Supports cache mounts and multi-stage builds more efficiently</li>
                        <li>Image is pushed to the local registry and deployed as a container</li>
                      </>
                    )}
                    {driver.name === 'gcp_cloud_build' && (
                      <>
                        <li>Source is uploaded to a GCS staging bucket</li>
                        <li>Google Cloud Build compiles the image remotely</li>
                        <li>Built image is stored in Artifact Registry and pulled for deployment</li>
                      </>
                    )}
                    {driver.name === 'aws_codebuild' && (
                      <>
                        <li>Source is uploaded to an S3 staging bucket</li>
                        <li>AWS CodeBuild compiles the image remotely</li>
                        <li>Built image is stored in ECR and pulled for deployment</li>
                      </>
                    )}
                  </ol>
                </div>
              )}

              {kind === 'scan' && (
                <div>
                  <h4 className="text-xs font-semibold text-heading uppercase tracking-wider mb-2">
                    How It Works
                  </h4>
                  <ol className="text-xs text-muted space-y-1 list-decimal list-inside">
                    <li>Enable scanning on a site in Build Configuration</li>
                    <li>Source code is analyzed before building the image</li>
                    <li>Findings are reported in the pipeline run logs</li>
                    <li>Optionally fail the build if issues exceed a severity threshold</li>
                  </ol>
                </div>
              )}

              {kind === 'build' && !driver.is_default && (
                <p className="text-xs text-muted">
                  To make this the default for all new sites, set <code className="font-mono bg-black/30 px-1 rounded">DEFAULT_BUILD_DRIVER={driver.name}</code> in your <code className="font-mono bg-black/30 px-1 rounded">.env</code> file.
                </p>
              )}
            </>
          )}

          {/* Not configured / unavailable — show setup steps */}
          {driver.status !== 'ready' && (
            <>
              {/* Required env vars */}
              {driver.required_env.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-heading uppercase tracking-wider mb-2">
                    Required Environment Variables
                  </h4>
                  <div className="space-y-1.5">
                    {driver.required_env.map((env) => (
                      <div
                        key={env.name}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-black/20 border border-white/5"
                      >
                        {env.is_set ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                        )}
                        <code className="text-xs font-mono flex-1">{env.name}</code>
                        <span className="text-[10px] text-muted">{env.is_set ? 'Configured' : 'Missing'}</span>
                        <CopyButton text={env.name} />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Setup hint */}
              {driver.setup_hint && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-500/5 border border-amber-500/10">
                  <Terminal className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-amber-300">{driver.setup_hint}</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

import { Link } from 'react-router-dom'
import {
  Server, GitBranch, Shield, Activity, Globe, Database,
  Layers, Boxes, Terminal, Lock, Cpu, Zap,
  GitPullRequest, Container, Eye, Bell, Key, ArrowRight,
  CheckCircle2, ChevronRight, ScanSearch, Cloud,
  XCircle, AlertTriangle, Sparkles, Users,
} from 'lucide-react'

/* ─── Typed terminal component ─────────────────────────── */

function TerminalBlock({ lines, title }: { lines: { text: string; color?: string }[]; title?: string }) {
  return (
    <div className="rounded-xl bg-[#0a0a0f] border border-white/[0.06] terminal-glow overflow-hidden">
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-white/[0.02] border-b border-white/[0.04]">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        {title && (
          <span className="ml-2 text-[11px] text-gray-600" style={{ fontFamily: 'var(--font-mono)' }}>
            {title}
          </span>
        )}
      </div>
      {/* Lines */}
      <div className="p-4 space-y-1" style={{ fontFamily: 'var(--font-mono)' }}>
        {lines.map((line, i) => (
          <div key={i} className={`text-xs leading-relaxed ${line.color || 'text-gray-400'}`}>
            {line.text}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ─── Feature data ─────────────────────────────────────── */

const CAPABILITIES = [
  {
    icon: Layers,
    title: 'Multi-Tenant',
    desc: 'Tenants, Workspaces, Sites — isolated hierarchy with inherited permissions.',
  },
  {
    icon: GitBranch,
    title: 'Git-Follow',
    desc: 'Auto-deploy on push from GitHub or GitLab with branch tracking.',
  },
  {
    icon: Boxes,
    title: 'Pipeline Engine',
    desc: 'Multi-stage pipelines: clone, build, scan, deploy, health-check.',
  },
  {
    icon: GitPullRequest,
    title: 'PR Previews',
    desc: 'Ephemeral environments per pull request with TTL cleanup.',
  },
  {
    icon: Activity,
    title: 'Health Monitoring',
    desc: 'Continuous checks, auto-restart on failure, event history.',
  },
  {
    icon: Globe,
    title: 'Custom Domains',
    desc: 'Attach domains with DNS verification and automatic routing.',
  },
  {
    icon: Database,
    title: 'Linked Services',
    desc: 'Provision Postgres, Redis per-site. Connection strings auto-injected.',
  },
  {
    icon: Shield,
    title: 'RBAC',
    desc: 'Fine-grained roles at tenant, workspace, and site level.',
  },
  {
    icon: ScanSearch,
    title: 'Security Scanning',
    desc: 'Semgrep built-in. Fail builds on severity with CWE/OWASP tagging.',
  },
  {
    icon: Cloud,
    title: 'Multi-Cloud Build',
    desc: 'Docker, BuildKit, GCP Cloud Build, AWS CodeBuild.',
  },
  {
    icon: Bell,
    title: 'Notifications',
    desc: 'Webhook, Slack, email for deploys, health alerts, pipeline status.',
  },
  {
    icon: Key,
    title: 'API Tokens',
    desc: 'Scoped, revocable, expirable tokens for CI/CD integration.',
  },
]

const PIPELINE_STAGES = [
  { name: 'Clone', icon: GitBranch, color: 'bg-blue-500', glow: 'shadow-blue-500/30' },
  { name: 'Build', icon: Container, color: 'bg-violet-500', glow: 'shadow-violet-500/30' },
  { name: 'Scan', icon: Eye, color: 'bg-amber-500', glow: 'shadow-amber-500/30' },
  { name: 'Deploy', icon: Zap, color: 'bg-emerald-500', glow: 'shadow-emerald-500/30' },
  { name: 'Health', icon: Activity, color: 'bg-cyan-500', glow: 'shadow-cyan-500/30' },
]

/* ─── Page ─────────────────────────────────────────────── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-gray-950 text-white overflow-x-hidden" style={{ fontFamily: 'var(--font-body)' }}>

      {/* ── Nav ──────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-950/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Server className="w-5 h-5 text-blue-400" />
            <span className="font-bold text-base tracking-tight" style={{ fontFamily: 'var(--font-display)' }}>
              Adhara Engine
            </span>
          </div>
          <div className="flex items-center gap-4">
            <a href="#problem" className="text-xs text-gray-500 hover:text-white transition-colors hidden sm:inline">Why</a>
            <a href="#capabilities" className="text-xs text-gray-500 hover:text-white transition-colors hidden sm:inline">Capabilities</a>
            <a href="#pipeline" className="text-xs text-gray-500 hover:text-white transition-colors hidden sm:inline">Pipeline</a>
            <a href="#api" className="text-xs text-gray-500 hover:text-white transition-colors hidden sm:inline">API</a>
            <Link
              to="/login"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-white text-gray-950 text-xs font-semibold rounded-lg hover:bg-gray-200 transition-colors"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Sign In <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero: Split layout ───────────────────────────── */}
      <section className="relative pt-28 pb-20 px-6 overflow-hidden">
        {/* Ambient glow orbs — strong enough to create a visible backdrop */}
        <div className="absolute top-0 left-1/4 w-[700px] h-[700px] bg-blue-600/30 rounded-full blur-[160px] pointer-events-none" />
        <div className="absolute top-20 right-1/4 w-[600px] h-[600px] bg-indigo-500/20 rounded-full blur-[140px] pointer-events-none" />
        <div className="absolute top-40 left-1/2 -translate-x-1/2 w-[400px] h-[400px] bg-cyan-500/10 rounded-full blur-[120px] pointer-events-none" />
        {/* Subtle grid — no noise overlay */}
        <div className="absolute inset-0 bg-grid pointer-events-none opacity-50" />

        <div className="max-w-6xl mx-auto relative z-10">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">

            {/* Left: Copy */}
            <div>
              <div
                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-300 text-xs font-medium mb-6"
                style={{ fontFamily: 'var(--font-mono)' }}
              >
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                v0.1.0 — self-hosted deployment platform
              </div>

              <h1
                className="text-4xl sm:text-5xl lg:text-[3.5rem] font-extrabold tracking-tight leading-[1.08] mb-5 text-white"
                style={{ fontFamily: 'var(--font-display)', textShadow: '0 2px 20px rgba(255,255,255,0.12), 0 0 40px rgba(59,130,246,0.15)' }}
              >
                Build with AI.
                <br />
                <span
                  className="text-shimmer bg-gradient-to-r from-blue-200 via-cyan-100 to-blue-300 bg-clip-text text-transparent"
                  style={{ textShadow: 'none' }}
                >
                  Deploy with confidence.
                </span>
              </h1>

              <p className="text-base text-gray-200 leading-relaxed mb-8 max-w-md">
                Building AI applications is the easy part. Getting them deployed, updated, and managed
                across teams is where things break down. Adhara Engine makes it as simple as <code className="text-blue-300" style={{ fontFamily: 'var(--font-mono)' }}>git push</code>.
              </p>

              <div className="flex items-center gap-3">
                <Link
                  to="/login"
                  className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-all hover:shadow-lg hover:shadow-blue-600/20"
                  style={{ fontFamily: 'var(--font-display)' }}
                >
                  Get Started <ArrowRight className="w-4 h-4" />
                </Link>
                <a
                  href="#capabilities"
                  className="inline-flex items-center gap-1.5 px-5 py-3 text-gray-400 hover:text-white text-sm font-medium transition-colors"
                >
                  Learn more <ChevronRight className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* Right: Terminal */}
            <div className="animate-float">
              <TerminalBlock
                title="adhara-engine"
                lines={[
                  { text: '$ adhara deploy --site my-app', color: 'text-gray-300' },
                  { text: '', color: 'text-gray-600' },
                  { text: '  Pipeline #47 started', color: 'text-blue-400' },
                  { text: '  ├─ clone    ✓  1.2s', color: 'text-emerald-400' },
                  { text: '  ├─ build    ✓  23.4s', color: 'text-emerald-400' },
                  { text: '  ├─ scan     ✓  8.1s  (0 findings)', color: 'text-emerald-400' },
                  { text: '  ├─ deploy   ✓  2.8s  (blue-green)', color: 'text-emerald-400' },
                  { text: '  └─ health   ✓  0.4s  (200 OK)', color: 'text-emerald-400' },
                  { text: '', color: 'text-gray-600' },
                  { text: '  ✓ Live at my-app.workspace.tenant.localhost', color: 'text-cyan-400' },
                  { text: '  ✓ 0 downtime — previous container cleaned up', color: 'text-gray-500' },
                ]}
              />
            </div>
          </div>

          {/* Stats strip */}
          <div className="mt-16 grid grid-cols-4 gap-px rounded-xl overflow-hidden border border-white/[0.04]">
            {[
              { value: '71', label: 'API Endpoints', mono: true },
              { value: '4', label: 'Build Drivers', mono: true },
              { value: '5', label: 'Pipeline Stages', mono: true },
              { value: '∞', label: 'Sites & Tenants', mono: false },
            ].map(({ value, label, mono }) => (
              <div key={label} className="bg-white/[0.02] px-4 py-5 text-center">
                <div
                  className="text-2xl font-bold text-white"
                  style={{ fontFamily: mono ? 'var(--font-mono)' : 'var(--font-display)' }}
                >
                  {value}
                </div>
                <div className="text-[11px] text-gray-500 mt-1">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── The Problem ──────────────────────────────────── */}
      <section id="problem" className="py-24 px-6 border-y border-white/5 bg-white/[0.01]">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-300 text-xs font-medium mb-6"
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              <AlertTriangle className="w-3 h-3" />
              The deployment bottleneck
            </div>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              AI made building apps easy.
              <br />
              <span className="text-gray-500">Deploying them? Not so much.</span>
            </h2>
            <p className="text-base text-gray-400 max-w-2xl mx-auto leading-relaxed">
              You can build an AI-powered application in an afternoon. But when it comes to getting it online,
              sharing it with users, updating it, and managing access — that's where teams get stuck.
            </p>
          </div>

          {/* Before / After comparison */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Without Adhara */}
            <div className="rounded-2xl border border-red-500/10 bg-red-500/[0.02] p-8">
              <div className="flex items-center gap-2 mb-6">
                <XCircle className="w-5 h-5 text-red-400" />
                <h3 className="text-lg font-semibold text-red-300" style={{ fontFamily: 'var(--font-display)' }}>
                  Traditional Deployment
                </h3>
              </div>
              <div className="space-y-4">
                {[
                  {
                    title: 'Write deployment scripts from scratch',
                    desc: 'Bash scripts, Dockerfiles, CI/CD pipelines, nginx configs — for every single app.',
                  },
                  {
                    title: 'Manually manage DNS and routing',
                    desc: 'Configure domains, set up reverse proxies, manage SSL certificates by hand.',
                  },
                  {
                    title: 'No visibility into what\'s running',
                    desc: 'SSH into servers to check if containers are alive. No health checks, no auto-restart.',
                  },
                  {
                    title: 'Everyone has root access or no access',
                    desc: 'No role-based permissions. Either the whole team can break production, or nobody can deploy.',
                  },
                  {
                    title: 'Updates mean downtime',
                    desc: 'Stop the old version, hope the new one starts. No blue-green deploys, no rollback.',
                  },
                  {
                    title: 'Each app is a snowflake',
                    desc: 'Different deploy process for every project. No standardization, no shared tooling.',
                  },
                ].map(({ title, desc }) => (
                  <div key={title} className="flex gap-3">
                    <div className="flex-shrink-0 w-1 rounded-full bg-red-500/30 mt-1" style={{ minHeight: '2.5rem' }} />
                    <div>
                      <div className="text-sm font-medium text-gray-200">{title}</div>
                      <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* With Adhara */}
            <div className="rounded-2xl border border-emerald-500/10 bg-emerald-500/[0.02] p-8">
              <div className="flex items-center gap-2 mb-6">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-emerald-300" style={{ fontFamily: 'var(--font-display)' }}>
                  With Adhara Engine
                </h3>
              </div>
              <div className="space-y-4">
                {[
                  {
                    title: 'Connect your repo, push, and it\'s live',
                    desc: 'Point Adhara at a GitHub or GitLab repo. Every push triggers an automatic build and deploy.',
                  },
                  {
                    title: 'Domains and routing handled automatically',
                    desc: 'Add custom domains through the dashboard. Routing, DNS verification, and proxy config are automatic.',
                  },
                  {
                    title: 'Real-time health monitoring and auto-recovery',
                    desc: 'Continuous health checks on every site. Automatic restart on failure with full event history.',
                  },
                  {
                    title: 'Role-based access at every level',
                    desc: 'Owner, Admin, Member, Viewer roles scoped to tenants, workspaces, or individual sites.',
                  },
                  {
                    title: 'Zero-downtime blue-green deploys',
                    desc: 'New version starts alongside old. Traffic switches only after health checks pass. Instant rollback.',
                  },
                  {
                    title: 'One platform for every app',
                    desc: 'Standard pipeline for all projects: clone → build → scan → deploy → health check. Consistent and reliable.',
                  },
                ].map(({ title, desc }) => (
                  <div key={title} className="flex gap-3">
                    <div className="flex-shrink-0 w-1 rounded-full bg-emerald-500/30 mt-1" style={{ minHeight: '2.5rem' }} />
                    <div>
                      <div className="text-sm font-medium text-gray-200">{title}</div>
                      <div className="text-xs text-gray-500 mt-0.5 leading-relaxed">{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────── */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              Three steps to production.
            </h2>
            <p className="text-base text-gray-400 max-w-xl mx-auto leading-relaxed">
              Whether you're deploying one AI chatbot or fifty internal tools, the workflow is the same.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              {
                step: '01',
                title: 'Connect your repository',
                desc: 'Link a GitHub or GitLab repo through the dashboard. Choose your branch, set a Dockerfile path, and configure environment variables. That\'s the only setup you\'ll ever do.',
                accent: 'blue',
                terminal: {
                  title: 'site config',
                  lines: [
                    { text: 'source:    github.com/acme/ai-chat', color: 'text-gray-300' },
                    { text: 'branch:    main', color: 'text-blue-400' },
                    { text: 'auto_deploy: true', color: 'text-emerald-400' },
                    { text: 'dockerfile: ./Dockerfile', color: 'text-gray-400' },
                  ],
                },
              },
              {
                step: '02',
                title: 'Push your code',
                desc: 'Every git push triggers an automatic pipeline: clone, build a container, run security scans, deploy with zero downtime, and verify health. All in under a minute.',
                accent: 'violet',
                terminal: {
                  title: 'git',
                  lines: [
                    { text: '$ git push origin main', color: 'text-gray-300' },
                    { text: '', color: 'text-gray-700' },
                    { text: 'Webhook received ✓', color: 'text-blue-400' },
                    { text: 'Pipeline #48 started...', color: 'text-violet-400' },
                  ],
                },
              },
              {
                step: '03',
                title: 'It\'s live — manage at scale',
                desc: 'Your app is deployed with health monitoring, custom domains, and RBAC. Invite team members with scoped permissions. Monitor, roll back, or scale — all from one dashboard.',
                accent: 'emerald',
                terminal: {
                  title: 'status',
                  lines: [
                    { text: 'ai-chat.acme.prod ● running', color: 'text-emerald-400' },
                    { text: 'health: 200 OK  (4ms)', color: 'text-emerald-400' },
                    { text: 'uptime: 14d 6h 32m', color: 'text-gray-400' },
                    { text: 'deploys: 23  (0 failed)', color: 'text-cyan-400' },
                  ],
                },
              },
            ].map(({ step, title, desc, accent, terminal }) => (
              <div key={step} className="flex flex-col">
                <div className={`text-5xl font-extrabold text-${accent}-500/20 mb-4`} style={{ fontFamily: 'var(--font-mono)' }}>
                  {step}
                </div>
                <h3 className="text-lg font-semibold text-white mb-2" style={{ fontFamily: 'var(--font-display)' }}>
                  {title}
                </h3>
                <p className="text-sm text-gray-400 leading-relaxed mb-5 flex-1">
                  {desc}
                </p>
                <TerminalBlock title={terminal.title} lines={terminal.lines} />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Who It's For ─────────────────────────────────── */}
      <section className="py-24 px-6 border-y border-white/5 bg-white/[0.01]">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-12 items-start">
            <div className="lg:sticky lg:top-24">
              <h2
                className="text-3xl font-bold tracking-tight mb-4 text-white"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Built for teams
                <br />
                <span className="text-blue-400">shipping AI applications.</span>
              </h2>
              <p className="text-sm text-gray-400 leading-relaxed">
                Whether you're a solo developer deploying side projects or an enterprise
                team managing dozens of AI-powered tools, Adhara Engine scales with you.
              </p>
            </div>

            <div className="space-y-5">
              {[
                {
                  icon: Sparkles,
                  title: 'AI Application Teams',
                  desc: 'You built a chatbot, a RAG pipeline, an AI agent, or an internal tool with Claude, GPT, or open-source models. Now you need it running 24/7 with real URLs, health monitoring, and the ability to push updates without downtime.',
                  color: 'text-violet-400',
                  border: 'border-violet-500/10',
                },
                {
                  icon: Users,
                  title: 'Organizations with Multiple Projects',
                  desc: 'You have 5, 10, or 50 different web applications across different teams. Each team needs their own workspace, their own permissions, and the ability to deploy independently — without stepping on each other.',
                  color: 'text-blue-400',
                  border: 'border-blue-500/10',
                },
                {
                  icon: Shield,
                  title: 'Security-Conscious Teams',
                  desc: 'You need every deployment scanned for vulnerabilities before it goes live. You need audit trails, scoped API tokens, and role-based access control — not everyone-has-root access.',
                  color: 'text-emerald-400',
                  border: 'border-emerald-500/10',
                },
                {
                  icon: Server,
                  title: 'Self-Hosted by Design',
                  desc: 'You don\'t want to send your code, environment variables, or API keys to a third-party platform. Adhara Engine runs entirely on your infrastructure — your servers, your data, your control.',
                  color: 'text-amber-400',
                  border: 'border-amber-500/10',
                },
              ].map(({ icon: Icon, title, desc, color, border }) => (
                <div key={title} className={`flex gap-4 p-5 rounded-xl border ${border} bg-white/[0.01] hover:bg-white/[0.03] transition-colors`}>
                  <div className="flex-shrink-0 mt-0.5">
                    <Icon className={`w-5 h-5 ${color}`} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-1" style={{ fontFamily: 'var(--font-display)' }}>{title}</h3>
                    <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Capabilities: Compact 2-col list ─────────────── */}
      <section id="capabilities" className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.5fr] gap-12 items-start">

            {/* Left: Sticky headline */}
            <div className="lg:sticky lg:top-24">
              <h2
                className="text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Everything you need
                <br />
                <span className="text-gray-500">to ship with confidence.</span>
              </h2>
              <p className="text-sm text-gray-500 leading-relaxed max-w-sm">
                12 feature modules. Zero vendor lock-in. Every capability backed
                by a documented REST endpoint.
              </p>
            </div>

            {/* Right: Feature list */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
              {CAPABILITIES.map(({ icon: Icon, title, desc }) => (
                <div key={title} className="flex gap-3 group">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.06] flex items-center justify-center group-hover:border-blue-500/30 group-hover:bg-blue-500/5 transition-colors">
                    <Icon className="w-4 h-4 text-gray-500 group-hover:text-blue-400 transition-colors" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-200" style={{ fontFamily: 'var(--font-display)' }}>{title}</h3>
                    <p className="text-xs text-gray-500 leading-relaxed mt-0.5">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Architecture: Nested layers ──────────────────── */}
      <section className="py-20 px-6 border-y border-white/5 bg-white/[0.01]">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">

            {/* Visual: Nested boxes */}
            <div className="relative">
              <div className="rounded-2xl border border-blue-500/20 bg-blue-500/[0.03] p-6">
                <div className="flex items-center gap-2 mb-3">
                  <Lock className="w-4 h-4 text-blue-400" />
                  <span className="text-sm font-semibold text-blue-400" style={{ fontFamily: 'var(--font-display)' }}>Tenant</span>
                  <span className="text-[10px] text-gray-600 ml-auto" style={{ fontFamily: 'var(--font-mono)' }}>acme-corp</span>
                </div>

                <div className="rounded-xl border border-purple-500/20 bg-purple-500/[0.03] p-5 ml-2">
                  <div className="flex items-center gap-2 mb-3">
                    <Boxes className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-semibold text-purple-400" style={{ fontFamily: 'var(--font-display)' }}>Workspace</span>
                    <span className="text-[10px] text-gray-600 ml-auto" style={{ fontFamily: 'var(--font-mono)' }}>production</span>
                  </div>

                  <div className="space-y-2 ml-2">
                    {[
                      { name: 'marketing-site', status: 'running', color: 'emerald' },
                      { name: 'docs-portal', status: 'running', color: 'emerald' },
                      { name: 'admin-panel', status: 'deploying', color: 'amber' },
                    ].map(site => (
                      <div key={site.name} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-white/[0.04] bg-white/[0.02]">
                        <span className={`w-2 h-2 rounded-full bg-${site.color}-400 ${site.status === 'deploying' ? 'animate-pulse' : ''}`} />
                        <span className="text-xs text-gray-300" style={{ fontFamily: 'var(--font-mono)' }}>{site.name}</span>
                        <span className={`ml-auto text-[10px] text-${site.color}-400`}>{site.status}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Copy */}
            <div>
              <h2
                className="text-3xl font-bold tracking-tight mb-4"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Built for
                <br />
                <span className="text-emerald-400">multi-tenancy.</span>
              </h2>
              <p className="text-sm text-gray-400 leading-relaxed mb-6">
                A three-tier hierarchy — Tenants, Workspaces, Sites — with full resource
                isolation, inherited RBAC permissions, and scoped API tokens at every level.
              </p>
              <div className="space-y-3">
                {[
                  'Tenant-level billing, members, and resource limits',
                  'Workspace-level project grouping and team access',
                  'Site-level git config, domains, env vars, and pipelines',
                  'Role inheritance: Owner → Admin → Member → Viewer',
                ].map(text => (
                  <div key={text} className="flex items-start gap-2.5">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-300">{text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Pipeline ─────────────────────────────────────── */}
      <section id="pipeline" className="py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight mb-3" style={{ fontFamily: 'var(--font-display)' }}>
              From <span className="text-violet-400">git push</span> to <span className="text-emerald-400">production</span>
            </h2>
            <p className="text-sm text-gray-500 max-w-lg mx-auto">
              Every deployment runs through a multi-stage pipeline with real-time visibility, security scanning, and zero-downtime blue-green deploys.
            </p>
          </div>

          {/* Pipeline stages — horizontal */}
          <div className="flex items-center justify-center gap-3 sm:gap-5 mb-10">
            {PIPELINE_STAGES.map(({ name, icon: Icon, color, glow }, i) => (
              <div key={name} className="flex items-center gap-3 sm:gap-5">
                <div className="flex flex-col items-center gap-2">
                  <div className={`w-14 h-14 rounded-2xl ${color} flex items-center justify-center shadow-lg ${glow}`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <span className="text-[11px] font-medium text-gray-400" style={{ fontFamily: 'var(--font-mono)' }}>{name}</span>
                </div>
                {i < PIPELINE_STAGES.length - 1 && (
                  <div className="w-8 h-px bg-gradient-to-r from-white/10 to-white/5 -mt-5" />
                )}
              </div>
            ))}
          </div>

          {/* Two-col: features + terminal */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mt-8">
            <div className="space-y-3 pt-2">
              {[
                { text: 'Real-time stage progress with streaming logs', color: 'text-blue-400' },
                { text: 'Automatic security scanning via Semgrep', color: 'text-amber-400' },
                { text: 'Blue-green zero-downtime container swaps', color: 'text-emerald-400' },
                { text: 'Configurable health check endpoints', color: 'text-cyan-400' },
                { text: 'Auto-rollback on health check failure', color: 'text-red-400' },
                { text: 'PR preview environments with TTL cleanup', color: 'text-violet-400' },
              ].map(({ text, color }) => (
                <div key={text} className="flex items-center gap-3">
                  <CheckCircle2 className={`w-4 h-4 ${color} flex-shrink-0`} />
                  <span className="text-sm text-gray-300">{text}</span>
                </div>
              ))}
            </div>

            <div className="animate-float-delayed">
              <TerminalBlock
                title="pipeline #47 — stages"
                lines={[
                  { text: 'Stage         Status    Duration', color: 'text-gray-600' },
                  { text: '────────────  ────────  ────────', color: 'text-gray-700' },
                  { text: 'clone         passed    1.2s', color: 'text-emerald-400' },
                  { text: 'build         passed    23.4s', color: 'text-emerald-400' },
                  { text: 'scan          passed    8.1s', color: 'text-emerald-400' },
                  { text: 'deploy        passed    2.8s', color: 'text-emerald-400' },
                  { text: 'health-check  passed    0.4s', color: 'text-emerald-400' },
                  { text: '', color: 'text-gray-700' },
                  { text: 'Result: SUCCESS  Total: 35.9s', color: 'text-cyan-300' },
                ]}
              />
            </div>
          </div>
        </div>
      </section>

      {/* ── Security Scanning ──────────────────────────────── */}
      <section className="py-24 px-6 border-t border-white/5 bg-gradient-to-b from-gray-950 via-[#0c0c14] to-gray-950 relative overflow-hidden">
        {/* Ambient glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-amber-500/[0.04] rounded-full blur-[150px] pointer-events-none" />

        <div className="max-w-6xl mx-auto relative z-10">
          {/* Section header */}
          <div className="text-center mb-16">
            <div
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs font-medium mb-5"
              style={{ fontFamily: 'var(--font-mono)' }}
            >
              <ScanSearch className="w-3.5 h-3.5" />
              Built-in security scanning
            </div>
            <h2
              className="text-3xl sm:text-4xl font-bold tracking-tight mb-4 text-white"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              AI writes fast.
              <br />
              <span className="text-amber-400">Security catches up.</span>
            </h2>
            <p className="text-base text-gray-400 max-w-2xl mx-auto leading-relaxed">
              When you're building with AI, code gets generated at an unprecedented pace. But speed
              without security is a liability — not a feature.
            </p>
          </div>

          {/* Risk cards + explanation */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-start mb-16">

            {/* Left: The problem */}
            <div>
              <h3
                className="text-xl font-semibold text-white mb-4"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                The real cost of unscanned code
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed mb-6">
                AI-generated code can introduce vulnerabilities that look correct at a glance but
                open doors to attackers. Without automated scanning in your deployment pipeline,
                every push to production is a gamble.
              </p>

              <div className="space-y-4">
                {[
                  {
                    icon: AlertTriangle,
                    title: 'Customer data breaches',
                    desc: 'SQL injection, broken authentication, exposed API keys — one overlooked vulnerability and your users\' data is compromised. Regulatory fines and lawsuits follow.',
                    color: 'text-red-400',
                    border: 'border-red-500/10',
                    bg: 'bg-red-500/[0.03]',
                  },
                  {
                    icon: XCircle,
                    title: 'System compromise and downtime',
                    desc: 'Remote code execution, server-side request forgery, insecure deserialization. Attackers gain control of your infrastructure. Your customers lose access.',
                    color: 'text-amber-400',
                    border: 'border-amber-500/10',
                    bg: 'bg-amber-500/[0.03]',
                  },
                  {
                    icon: Shield,
                    title: 'Legal and compliance exposure',
                    desc: 'SOC 2, HIPAA, GDPR — all require demonstrable security practices. "We didn\'t scan it" is not a defense. You need audit trails that prove every deploy was checked.',
                    color: 'text-violet-400',
                    border: 'border-violet-500/10',
                    bg: 'bg-violet-500/[0.03]',
                  },
                ].map(({ icon: Icon, title, desc, color, border, bg }) => (
                  <div key={title} className={`flex gap-4 p-4 rounded-xl border ${border} ${bg}`}>
                    <div className="flex-shrink-0 mt-0.5">
                      <Icon className={`w-5 h-5 ${color}`} />
                    </div>
                    <div>
                      <h4 className="text-sm font-semibold text-white mb-1" style={{ fontFamily: 'var(--font-display)' }}>
                        {title}
                      </h4>
                      <p className="text-xs text-gray-400 leading-relaxed">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: The solution — terminal + explanation */}
            <div>
              <h3
                className="text-xl font-semibold text-white mb-4"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                Scanning built into every deploy
              </h3>
              <p className="text-sm text-gray-400 leading-relaxed mb-6">
                Adhara Engine runs Semgrep on every deployment automatically. Vulnerabilities are caught
                before code goes live — not after a breach. Configure severity thresholds, and builds
                fail when critical issues are found.
              </p>

              <TerminalBlock
                title="scan — pipeline #47"
                lines={[
                  { text: '$ semgrep --config auto --json ./src', color: 'text-gray-400' },
                  { text: '', color: 'text-gray-700' },
                  { text: '  Scanning 143 files...', color: 'text-blue-400' },
                  { text: '', color: 'text-gray-700' },
                  { text: '  ✗ sql-injection (CWE-89)  HIGH', color: 'text-red-400' },
                  { text: '    src/api/users.py:42', color: 'text-gray-500' },
                  { text: '    f"SELECT * FROM users WHERE id={user_id}"', color: 'text-red-300' },
                  { text: '', color: 'text-gray-700' },
                  { text: '  ✗ hardcoded-secret (CWE-798)  HIGH', color: 'text-red-400' },
                  { text: '    src/config.py:7', color: 'text-gray-500' },
                  { text: '    API_KEY = "sk-live-a8f3b..."', color: 'text-red-300' },
                  { text: '', color: 'text-gray-700' },
                  { text: '  ⚠ open-redirect (CWE-601)  MEDIUM', color: 'text-amber-400' },
                  { text: '    src/auth/callback.py:18', color: 'text-gray-500' },
                  { text: '', color: 'text-gray-700' },
                  { text: '  Findings: 2 HIGH, 1 MEDIUM, 0 LOW', color: 'text-amber-300' },
                  { text: '  Policy: FAIL on HIGH severity', color: 'text-red-400' },
                  { text: '  Result: BLOCKED — fix before deploy', color: 'text-red-400' },
                ]}
              />

              <div className="mt-5 grid grid-cols-2 gap-3">
                {[
                  { label: 'OWASP Top 10', value: 'Full coverage' },
                  { label: 'CWE tagging', value: 'Per finding' },
                  { label: 'Severity gate', value: 'Configurable' },
                  { label: 'Audit trail', value: 'Every deploy' },
                ].map(({ label, value }) => (
                  <div key={label} className="px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <div className="text-[10px] text-gray-500 uppercase tracking-wider" style={{ fontFamily: 'var(--font-mono)' }}>
                      {label}
                    </div>
                    <div className="text-xs text-white font-medium mt-0.5">{value}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom callout */}
          <div className="rounded-2xl border border-amber-500/10 bg-amber-500/[0.03] p-8 text-center">
            <p className="text-base text-gray-200 leading-relaxed max-w-2xl mx-auto">
              Traditional deployment workflows skip scanning entirely. Adhara Engine makes it
              <strong className="text-white"> impossible to deploy unscanned code</strong>. Every push
              runs through Semgrep. Every finding is tagged with CWE and OWASP references.
              Every deploy has a security audit trail — because when you're shipping AI-generated code
              at speed, <strong className="text-white">the safety net has to be automatic</strong>.
            </p>
          </div>
        </div>
      </section>

      {/* ── API: Asymmetric showcase ─────────────────────── */}
      <section id="api" className="py-20 px-6 border-y border-white/5 bg-white/[0.01]">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] gap-10 items-start">

            {/* Left: API terminal */}
            <div>
              <TerminalBlock
                title="curl — deploy via API"
                lines={[
                  { text: '$ curl -s -X POST \\', color: 'text-gray-300' },
                  { text: '    http://engine.localhost/api/v1/sites/abc/deploy \\', color: 'text-gray-300' },
                  { text: '    -H "Authorization: Bearer $TOKEN" | jq', color: 'text-gray-300' },
                  { text: '', color: 'text-gray-700' },
                  { text: '{', color: 'text-gray-500' },
                  { text: '  "pipeline_run_id": "pr_8f3a...",', color: 'text-blue-400' },
                  { text: '  "status": "pending",', color: 'text-amber-400' },
                  { text: '  "trigger": "api",', color: 'text-gray-400' },
                  { text: '  "stages": ["clone","build","scan","deploy","health"]', color: 'text-emerald-400' },
                  { text: '}', color: 'text-gray-500' },
                ]}
              />

              <div className="flex flex-wrap gap-1.5 mt-4">
                {['tenants', 'workspaces', 'sites', 'pipelines', 'domains', 'health', 'previews', 'tokens', 'services', 'members'].map(ep => (
                  <span
                    key={ep}
                    className="px-2 py-1 rounded-md bg-white/[0.03] border border-white/[0.05] text-[10px] text-gray-500"
                    style={{ fontFamily: 'var(--font-mono)' }}
                  >
                    /api/v1/{ep}
                  </span>
                ))}
              </div>
            </div>

            {/* Right: Copy */}
            <div className="lg:pt-4">
              <div className="flex items-center gap-2 mb-4">
                <Terminal className="w-5 h-5 text-blue-400" />
                <span className="text-xs font-semibold text-blue-300 uppercase tracking-wider" style={{ fontFamily: 'var(--font-mono)' }}>
                  API-First
                </span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight mb-4" style={{ fontFamily: 'var(--font-display)' }}>
                71 endpoints.
                <br />
                <span className="text-gray-500">Full REST API.</span>
              </h2>
              <p className="text-sm text-gray-400 leading-relaxed mb-6">
                Every action in the dashboard is backed by a documented API. Automate deployments,
                manage infrastructure, and integrate with CI/CD through scoped API tokens.
              </p>
              <div className="space-y-2.5">
                {[
                  'OpenAPI / Swagger documentation at /docs',
                  'Scoped API tokens with fine-grained permissions',
                  'Webhook integration for GitHub & GitLab',
                  'Full CRUD on every resource in the hierarchy',
                ].map(text => (
                  <div key={text} className="flex items-start gap-2.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" />
                    <span className="text-xs text-gray-400">{text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Tech stack: Horizontal scroll ────────────────── */}
      <section className="py-16 px-6">
        <div className="max-w-6xl mx-auto">
          <h3
            className="text-xs font-semibold text-gray-600 uppercase tracking-widest mb-6 text-center"
            style={{ fontFamily: 'var(--font-mono)' }}
          >
            Powered by
          </h3>
          <div className="flex items-center justify-center flex-wrap gap-6">
            {[
              'FastAPI', 'PostgreSQL', 'Redis', 'Docker', 'React 19', 'Zitadel', 'Traefik', 'Semgrep',
            ].map(tech => (
              <span
                key={tech}
                className="text-sm text-gray-600 hover:text-gray-300 transition-colors cursor-default"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────── */}
      <section className="py-20 px-6">
        <div className="max-w-2xl mx-auto text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600/10 border border-blue-500/20 mb-6">
            <Cpu className="w-6 h-6 text-blue-400" />
          </div>
          <h2
            className="text-3xl font-bold tracking-tight mb-4"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Your infrastructure.
            <br />
            Your deployments.
          </h2>
          <p className="text-sm text-gray-500 max-w-md mx-auto mb-8 leading-relaxed">
            Deploy Adhara Engine on your infrastructure and take full ownership
            of your entire deployment pipeline.
          </p>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-white text-gray-950 font-semibold rounded-xl transition-all hover:bg-gray-200 hover:shadow-lg"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Start Deploying <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="border-t border-white/5 py-6 px-6">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-gray-600 text-xs">
            <Server className="w-3.5 h-3.5" />
            <span style={{ fontFamily: 'var(--font-mono)' }}>adhara-engine v0.1.0</span>
          </div>
          <div className="text-[11px] text-gray-600">
            Copyright 2026 EIM Global Solutions, LLC. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  )
}

import { useAuth } from 'react-oidc-context'
import { Navigate, useNavigate } from 'react-router-dom'
import { Server, LogIn, AlertTriangle, Terminal, Key } from 'lucide-react'
import { useState, useEffect } from 'react'
import { OIDC_ENABLED, useTokenAuth } from '../auth/AuthProvider'

function SetupGuide() {
  return (
    <div className="w-full max-w-lg mx-auto mt-8">
      <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-6">
        <div className="flex items-center gap-3 mb-4">
          <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0" />
          <h3 className="font-semibold text-amber-300" style={{ fontFamily: 'var(--font-display)' }}>
            Authentication Not Configured
          </h3>
        </div>
        <p className="text-sm text-gray-400 mb-5 leading-relaxed">
          Adhara Engine uses Zitadel for OIDC authentication. Follow these steps to get set up:
        </p>

        <div className="space-y-3">
          {[
            {
              step: '1',
              title: 'Start the full stack',
              cmd: 'make init',
              desc: 'Starts all services including Zitadel',
            },
            {
              step: '2',
              title: 'Run the Zitadel setup wizard',
              cmd: 'bash scripts/setup-zitadel.sh',
              desc: 'Creates the OIDC application and writes your Client ID',
            },
            {
              step: '3',
              title: 'Create a user account',
              cmd: 'bash scripts/create-user.sh',
              desc: 'Interactive wizard to create admin or normal users',
            },
            {
              step: '4',
              title: 'Restart the UI',
              cmd: 'docker compose restart ui',
              desc: 'Picks up the new OIDC configuration',
            },
          ].map(({ step, title, cmd, desc }) => (
            <div key={step} className="flex gap-3">
              <div className="flex-shrink-0 w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/30 flex items-center justify-center">
                <span className="text-xs font-bold text-blue-400">{step}</span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-200">{title}</div>
                <code
                  className="block mt-1 px-3 py-1.5 rounded-lg bg-black/40 border border-white/5 text-xs text-emerald-400 overflow-x-auto"
                  style={{ fontFamily: 'var(--font-mono)' }}
                >
                  $ {cmd}
                </code>
                <div className="text-xs text-gray-500 mt-1">{desc}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-5 pt-4 border-t border-white/5">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Terminal className="w-3 h-3" />
            <span>See <code className="text-gray-400" style={{ fontFamily: 'var(--font-mono)' }}>README.md</code> for full setup documentation</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function ConnectionStatus() {
  const [apiOk, setApiOk] = useState<boolean | null>(null)
  const [zitadelOk, setZitadelOk] = useState<boolean | null>(null)
  const [clientId, setClientId] = useState<string | null>(null)

  useEffect(() => {
    fetch('/health')
      .then(r => { setApiOk(r.ok); return r.json() })
      .catch(() => setApiOk(false))

    const issuer = import.meta.env.VITE_OIDC_ISSUER || 'http://localhost:3001'
    const cid = import.meta.env.VITE_OIDC_CLIENT_ID || ''
    setClientId(cid || null)

    fetch(`${issuer}/.well-known/openid-configuration`)
      .then(r => setZitadelOk(r.ok))
      .catch(() => setZitadelOk(false))
  }, [])

  const items = [
    { label: 'API Backend', ok: apiOk },
    { label: 'OIDC Provider', ok: zitadelOk },
    { label: 'Client ID', ok: clientId ? true : false },
  ]

  return (
    <div className="flex items-center justify-center gap-4 mt-6">
      {items.map(({ label, ok }) => (
        <div key={label} className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${ok === null ? 'bg-gray-600 animate-pulse' : ok ? 'bg-emerald-400' : 'bg-red-400'}`} />
          <span className="text-[11px] text-gray-500">{label}</span>
        </div>
      ))}
    </div>
  )
}

// ── Token Login (no Zitadel) ─────────────────────────────────────

function TokenLogin() {
  const { isAuthenticated, login } = useTokenAuth()
  const navigate = useNavigate()
  const [token, setToken] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    const trimmed = token.trim()
    if (!trimmed) {
      setError('Please enter an API token')
      return
    }

    setChecking(true)
    try {
      // Validate the token against the API
      const res = await fetch('/health', {
        headers: { Authorization: `Bearer ${trimmed}` },
      })
      if (!res.ok) {
        setError('Invalid token or API unreachable')
        setChecking(false)
        return
      }
      login(trimmed)
      navigate('/dashboard', { replace: true })
    } catch {
      setError('Could not connect to API')
      setChecking(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-6 relative noise-overlay bg-grid">
      <div className="relative z-10 w-full max-w-lg">
        {/* Logo + Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 mb-6">
            <Server className="w-8 h-8 text-blue-400" />
          </div>
          <h1
            className="text-4xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Adhara Engine
          </h1>
          <p className="text-gray-500 mt-2 text-sm">
            Self-hosted deployment platform
          </p>
        </div>

        {/* Token Sign In Card */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm p-8">
          <p className="text-gray-400 text-center text-sm mb-6 leading-relaxed">
            Enter your API token to manage sites, deployments, and infrastructure.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="token" className="block text-xs font-medium text-gray-400 mb-1.5">
                API Token
              </label>
              <input
                id="token"
                type="password"
                value={token}
                onChange={e => setToken(e.target.value)}
                placeholder="ae_..."
                autoFocus
                className="w-full px-4 py-2.5 rounded-xl bg-black/40 border border-white/10 text-white placeholder-gray-600
                           focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 text-sm"
                style={{ fontFamily: 'var(--font-mono)' }}
              />
            </div>

            <button
              type="submit"
              disabled={checking}
              className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold
                         hover:bg-blue-500 active:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ fontFamily: 'var(--font-display)' }}
            >
              <Key className="w-5 h-5" />
              {checking ? 'Verifying...' : 'Sign In with Token'}
            </button>
          </form>

          {error && (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          <div className="mt-5 pt-4 border-t border-white/5">
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Terminal className="w-3 h-3" />
              <span>Generate a token with <code className="text-gray-400" style={{ fontFamily: 'var(--font-mono)' }}>make token</code></span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-8">
          <p className="text-[11px] text-gray-600">
            Copyright 2026 EIM Global Solutions, LLC
          </p>
        </div>
      </div>
    </div>
  )
}

// ── OIDC Login (Zitadel configured) ─────────────────────────────

function OidcLogin() {
  const auth = useAuth()

  if (auth.isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  const authError = auth.error
  const hasError = !!authError
  const isFetchError = hasError && authError != null && (
    authError.message.includes('Failed to fetch') ||
    authError.message.includes('NetworkError') ||
    authError.message.includes('Load failed')
  )
  const isCryptoError = hasError && authError != null &&
    authError.message.includes('Crypto')
  const isConfigError = !import.meta.env.VITE_OIDC_CLIENT_ID

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center px-6 relative noise-overlay bg-grid">
      <div className="relative z-10 w-full max-w-lg">
        {/* Logo + Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-600/10 border border-blue-500/20 mb-6">
            <Server className="w-8 h-8 text-blue-400" />
          </div>
          <h1
            className="text-4xl font-bold text-white tracking-tight"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            Adhara Engine
          </h1>
          <p className="text-gray-500 mt-2 text-sm">
            Self-hosted deployment platform
          </p>
        </div>

        {/* Sign In Card */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-sm p-8">
          <p className="text-gray-400 text-center text-sm mb-6 leading-relaxed">
            Sign in with your organization credentials to manage sites, deployments, and infrastructure.
          </p>

          <button
            onClick={() => auth.signinRedirect()}
            disabled={auth.isLoading}
            className="w-full inline-flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-semibold
                       hover:bg-blue-500 active:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            style={{ fontFamily: 'var(--font-display)' }}
          >
            <LogIn className="w-5 h-5" />
            {auth.isLoading ? 'Redirecting...' : 'Sign In with SSO'}
          </button>

          {/* Error display */}
          {isCryptoError && (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-amber-300">
                HTTPS required for sign-in. Configure a domain and run{' '}
                <code className="text-amber-200">sudo bash scripts/adhara-secure.sh</code>
              </p>
            </div>
          )}
          {hasError && !isFetchError && !isConfigError && !isCryptoError && (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-red-300">{authError?.message}</p>
            </div>
          )}
        </div>

        {/* Connection status indicators */}
        <ConnectionStatus />

        {/* Setup guide when auth backend is not reachable */}
        {(isFetchError || isConfigError) && <SetupGuide />}

        {/* Footer */}
        <div className="text-center mt-8">
          <p className="text-[11px] text-gray-600">
            Copyright 2026 EIM Global Solutions, LLC
          </p>
        </div>
      </div>
    </div>
  )
}

export default function Login() {
  if (OIDC_ENABLED) {
    return <OidcLogin />
  }
  return <TokenLogin />
}

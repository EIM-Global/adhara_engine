import { AuthProvider as OidcAuthProvider } from 'react-oidc-context'
import { oidcConfig } from './config'
import { setTokenGetter } from '../api/client'
import { useAuth } from 'react-oidc-context'
import { useEffect, createContext, useContext, useState, type ReactNode } from 'react'

// ── Token auth context (used when Zitadel is not configured) ────

interface TokenAuthState {
  isAuthenticated: boolean
  isLoading: boolean
  token: string | null
  login: (token: string) => void
  logout: () => void
}

const TokenAuthContext = createContext<TokenAuthState>({
  isAuthenticated: false,
  isLoading: false,
  token: null,
  login: () => {},
  logout: () => {},
})

export function useTokenAuth() {
  return useContext(TokenAuthContext)
}

function TokenAuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (token) {
      setTokenGetter(() => token)
    } else {
      setTokenGetter(null)
    }
    setIsLoading(false)
  }, [token])

  const login = (newToken: string) => {
    setToken(newToken)
    setTokenGetter(() => newToken)
  }

  const logout = () => {
    setToken(null)
    setTokenGetter(null)
  }

  return (
    <TokenAuthContext.Provider
      value={{
        isAuthenticated: !!token,
        isLoading,
        token,
        login,
        logout,
      }}
    >
      {children}
    </TokenAuthContext.Provider>
  )
}

// ── OIDC token sync (used when Zitadel IS configured) ───────────

function TokenSync({ children }: { children: ReactNode }) {
  const auth = useAuth()

  useEffect(() => {
    setTokenGetter(() => auth.user?.access_token)
    return () => setTokenGetter(null)
  }, [auth.user?.access_token])

  return <>{children}</>
}

function onSigninCallback() {
  window.history.replaceState({}, document.title, '/dashboard')
}

// ── Detect auth mode ────────────────────────────────────────────

const OIDC_ENABLED = !!(
  import.meta.env.VITE_OIDC_CLIENT_ID &&
  import.meta.env.VITE_OIDC_CLIENT_ID.trim()
)

export { OIDC_ENABLED }

export default function AuthProvider({ children }: { children: ReactNode }) {
  if (!OIDC_ENABLED) {
    return <TokenAuthProvider>{children}</TokenAuthProvider>
  }

  return (
    <OidcAuthProvider {...oidcConfig} onSigninCallback={onSigninCallback}>
      <TokenSync>{children}</TokenSync>
    </OidcAuthProvider>
  )
}

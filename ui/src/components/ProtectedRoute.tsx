import { useAuth } from 'react-oidc-context'
import { Navigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { OIDC_ENABLED, useTokenAuth } from '../auth/AuthProvider'

function OidcProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth()

  if (auth.isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (!auth.isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function TokenProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useTokenAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (OIDC_ENABLED) {
    return <OidcProtectedRoute>{children}</OidcProtectedRoute>
  }
  return <TokenProtectedRoute>{children}</TokenProtectedRoute>
}

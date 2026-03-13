import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from 'react-oidc-context'
import AuthProvider from './auth/AuthProvider'
import ThemeProvider from './components/ThemeProvider'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Tenants from './pages/Tenants'
import TenantDetail from './pages/TenantDetail'
import WorkspaceDetail from './pages/WorkspaceDetail'
import SiteDetail from './pages/SiteDetail'
import Ports from './pages/Ports'
import Sites from './pages/Sites'
import Services from './pages/Services'
import Registry from './pages/Registry'
import RegistryDetail from './pages/RegistryDetail'
import APITokens from './pages/APITokens'
import Settings from './pages/Settings'
import LandingPage from './pages/LandingPage'
import Login from './pages/Login'

function AuthCallback() {
  const auth = useAuth()

  if (auth.isAuthenticated) {
    return <Navigate to="/dashboard" replace />
  }

  if (auth.error) {
    return (
      <div className="min-h-screen bg-gray-950 flex flex-col items-center justify-center gap-4">
        <p className="text-red-400">Sign in failed: {auth.error.message}</p>
        <a href="/login" className="text-blue-400 hover:underline">Back to login</a>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <p className="text-gray-400">Completing sign in...</p>
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
    <AuthProvider>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/sites" element={<Sites />} />
          <Route path="/services" element={<Services />} />
          <Route path="/registry" element={<Registry />} />
          <Route path="/registry/:repo" element={<RegistryDetail />} />
          <Route path="/tenants" element={<Tenants />} />
          <Route path="/tenants/:tenantId" element={<TenantDetail />} />
          <Route path="/workspaces/:workspaceId" element={<WorkspaceDetail />} />
          <Route path="/sites/:siteId" element={<SiteDetail />} />
          <Route path="/ports" element={<Ports />} />
          <Route path="/tokens" element={<APITokens />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Routes>
    </AuthProvider>
    </ThemeProvider>
  )
}

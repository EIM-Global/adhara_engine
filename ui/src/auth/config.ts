import type { UserManagerSettings } from 'oidc-client-ts'

export const oidcConfig: UserManagerSettings = {
  authority: import.meta.env.VITE_OIDC_ISSUER || 'http://localhost:3001',
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID || '',
  redirect_uri: `${window.location.origin}/auth/callback`,
  post_logout_redirect_uri: window.location.origin,
  scope: 'openid profile email',
  response_type: 'code',
}

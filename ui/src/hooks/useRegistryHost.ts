import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

/**
 * Returns the registry host for push/pull commands.
 * Fetches from platform config API (which resolves ADHARA_DOMAIN → registry.DOMAIN
 * for HTTPS mode). In local/HTTP mode, derives from the browser's current
 * hostname — the registry is routed through Traefik at /v2/ on port 80.
 */
export function useRegistryHost(): string {
  const { data } = useQuery({
    queryKey: ['platform-config'],
    queryFn: api.getPlatformConfig,
    staleTime: 5 * 60 * 1000, // cache 5 min
  });

  if (data?.registry_host) return data.registry_host;

  // Derive from current page location — registry is routed through Traefik
  return window.location.hostname;
}

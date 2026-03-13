import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';

/**
 * Returns the registry host for push/pull commands.
 * Fetches from platform config API (which resolves ADHARA_DOMAIN → registry.DOMAIN
 * for HTTPS mode, or falls back to IP:5000 for HTTP mode).
 * Returns a fallback while loading so UI never shows empty strings.
 */
export function useRegistryHost(): string {
  const { data } = useQuery({
    queryKey: ['platform-config'],
    queryFn: api.getPlatformConfig,
    staleTime: 5 * 60 * 1000, // cache 5 min
  });

  if (data?.registry_host) return data.registry_host;

  // Fallback while loading: derive from current page location
  return `${window.location.hostname}:5000`;
}

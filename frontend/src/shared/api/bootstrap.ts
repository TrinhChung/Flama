import { hashKey, useQuery, type QueryClient } from '@tanstack/react-query'
import { appApi } from '../../app/api'
import { setCsrfToken } from './client'

export const bootstrapQueryKey = ['frontend', 'bootstrap'] as const

export async function fetchBootstrap() {
  const payload = await appApi.getBootstrap()
  setCsrfToken(payload.csrf_token)
  return payload
}

export function useBootstrap() {
  return useQuery({
    queryKey: bootstrapQueryKey,
    queryFn: fetchBootstrap,
    staleTime: Number.POSITIVE_INFINITY,
  })
}

/**
 * Query keys are not scoped by account, so a sign-in or sign-out must drop
 * everything cached for the previous account. The bootstrap entry stays: the
 * caller sets its new user and mounted shells keep observing it.
 */
export function clearAccountQueries(queryClient: QueryClient) {
  const bootstrapHash = hashKey(bootstrapQueryKey)
  queryClient.removeQueries({ predicate: (query) => query.queryHash !== bootstrapHash })
}

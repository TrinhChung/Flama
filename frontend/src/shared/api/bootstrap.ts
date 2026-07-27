import { useQuery } from '@tanstack/react-query'
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

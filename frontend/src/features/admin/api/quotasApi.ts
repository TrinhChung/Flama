import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiJson, apiRequest } from '@/shared/api/client'
import type {
  QuotaKind,
  QuotaOverridePayload,
  QuotaOverview,
  QuotaPeriod,
  QuotaPolicy,
  QuotaPolicyPayload,
  QuotaUser,
  QuotaUserDetail,
} from '../types/quotas'

const BASE = '/api/admin/quotas'
const QUOTAS_KEY = ['admin', 'quotas'] as const

export function fetchQuotaOverview(period: QuotaPeriod): Promise<QuotaOverview> {
  return apiRequest<QuotaOverview>(`${BASE}?period=${encodeURIComponent(period)}`)
}

export function updateQuotaPolicy(kind: QuotaKind, payload: QuotaPolicyPayload) {
  return apiJson<{ policy: QuotaPolicy; message: string }>(`${BASE}/policies/${kind}`, 'PUT', payload)
}

export function fetchQuotaUserDetail(userId: number): Promise<QuotaUserDetail> {
  return apiRequest<QuotaUserDetail>(`${BASE}/users/${userId}`)
}

export function upsertUserQuota(userId: number, kind: QuotaKind, payload: QuotaOverridePayload) {
  return apiJson<QuotaUserDetail & { message: string }>(`${BASE}/users/${userId}/${kind}`, 'PUT', payload)
}

export function deleteUserQuota(userId: number, kind: QuotaKind) {
  return apiJson<QuotaUserDetail & { message: string }>(`${BASE}/users/${userId}/${kind}`, 'DELETE')
}

export async function searchQuotaUsers(query: string): Promise<QuotaUser[]> {
  const result = await apiRequest<{ items: QuotaUser[] }>(
    `${BASE}/users/search?q=${encodeURIComponent(query)}`,
  )
  return result?.items ?? []
}

export function useQuotaOverview(period: QuotaPeriod) {
  return useQuery({
    queryKey: [...QUOTAS_KEY, 'overview', period],
    queryFn: () => fetchQuotaOverview(period),
    staleTime: 15_000,
  })
}

export function useQuotaUserDetail(userId: number | null) {
  return useQuery({
    queryKey: [...QUOTAS_KEY, 'user', userId],
    queryFn: () => fetchQuotaUserDetail(userId as number),
    enabled: userId !== null,
  })
}

export function useQuotaUserSearchQuery(term: string) {
  return useQuery({
    queryKey: [...QUOTAS_KEY, 'search', term],
    queryFn: () => searchQuotaUsers(term),
    enabled: term.length >= 2,
    staleTime: 30_000,
  })
}

export function useUpdateQuotaPolicy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ kind, payload }: { kind: QuotaKind; payload: QuotaPolicyPayload }) =>
      updateQuotaPolicy(kind, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: QUOTAS_KEY }),
  })
}

export function useSaveUserQuota() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, kind, payload }: { userId: number; kind: QuotaKind; payload: QuotaOverridePayload }) =>
      upsertUserQuota(userId, kind, payload),
    onSuccess: (detail) => {
      queryClient.setQueryData([...QUOTAS_KEY, 'user', detail.user.id], detail)
      return queryClient.invalidateQueries({ queryKey: [...QUOTAS_KEY, 'overview'] })
    },
  })
}

export function useDeleteUserQuota() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, kind }: { userId: number; kind: QuotaKind }) => deleteUserQuota(userId, kind),
    onSuccess: (detail) => {
      queryClient.setQueryData([...QUOTAS_KEY, 'user', detail.user.id], detail)
      return queryClient.invalidateQueries({ queryKey: [...QUOTAS_KEY, 'overview'] })
    },
  })
}

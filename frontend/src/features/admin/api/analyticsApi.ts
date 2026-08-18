import { useQuery } from '@tanstack/react-query'
import { apiRequest } from '@/shared/api/client'
import type {
  AnalyticsOverviewResponse,
  ContentGrowthResponse,
  RetentionCohortsResponse,
  StudyTimeResponse,
  UserGrowthResponse,
} from '../types/analytics'

export type AnalyticsQueryParams = {
  range?: string
  startDate?: string
  endDate?: string
}

function buildQueryString(params: AnalyticsQueryParams): string {
  const searchParams = new URLSearchParams()
  if (params.range) searchParams.set('range', params.range)
  if (params.startDate) searchParams.set('start_date', params.startDate)
  if (params.endDate) searchParams.set('end_date', params.endDate)
  const qs = searchParams.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAnalyticsOverview(
  params: AnalyticsQueryParams,
): Promise<AnalyticsOverviewResponse> {
  return apiRequest<AnalyticsOverviewResponse>(`/api/admin/analytics/overview${buildQueryString(params)}`)
}

export async function fetchUserGrowth(
  params: AnalyticsQueryParams,
): Promise<UserGrowthResponse> {
  return apiRequest<UserGrowthResponse>(`/api/admin/analytics/growth${buildQueryString(params)}`)
}

export async function fetchStudyTime(
  params: AnalyticsQueryParams,
): Promise<StudyTimeResponse> {
  return apiRequest<StudyTimeResponse>(`/api/admin/analytics/study-time${buildQueryString(params)}`)
}

export async function fetchContentGrowth(
  params: AnalyticsQueryParams,
): Promise<ContentGrowthResponse> {
  return apiRequest<ContentGrowthResponse>(`/api/admin/analytics/content-growth${buildQueryString(params)}`)
}

export async function fetchRetentionCohorts(
  weeks = 8,
): Promise<RetentionCohortsResponse> {
  return apiRequest<RetentionCohortsResponse>(`/api/admin/analytics/retention-cohorts?weeks=${weeks}`)
}

export function useAnalyticsOverview(params: AnalyticsQueryParams) {
  return useQuery({
    queryKey: ['admin', 'analytics', 'overview', params],
    queryFn: () => fetchAnalyticsOverview(params),
    staleTime: 60_000,
  })
}

export function useUserGrowth(params: AnalyticsQueryParams) {
  return useQuery({
    queryKey: ['admin', 'analytics', 'growth', params],
    queryFn: () => fetchUserGrowth(params),
    staleTime: 60_000,
  })
}

export function useStudyTime(params: AnalyticsQueryParams) {
  return useQuery({
    queryKey: ['admin', 'analytics', 'study-time', params],
    queryFn: () => fetchStudyTime(params),
    staleTime: 60_000,
  })
}

export function useContentGrowth(params: AnalyticsQueryParams) {
  return useQuery({
    queryKey: ['admin', 'analytics', 'content-growth', params],
    queryFn: () => fetchContentGrowth(params),
    staleTime: 60_000,
  })
}

export function useRetentionCohorts(weeks = 8) {
  return useQuery({
    queryKey: ['admin', 'analytics', 'retention-cohorts', weeks],
    queryFn: () => fetchRetentionCohorts(weeks),
    staleTime: 300_000,
  })
}

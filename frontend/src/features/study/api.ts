import { apiJson, apiJsonKeepalive, apiRequest } from '@/shared/api/client'
import { resolveBackendUrl } from '@/shared/config/env'
import type { StudyArtifactRef } from './types'

type StudyMutationMethod = 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/** Study endpoints all live under `/api`, resolved against the backend origin. */
export const studyApi = {
  get<T>(path: string): Promise<T> {
    return apiRequest<T>(resolveBackendUrl(path))
  },
  mutate<T>(path: string, method: StudyMutationMethod, body?: unknown): Promise<T> {
    return apiJson<T>(resolveBackendUrl(path), method, body)
  },
  mutateKeepalive<T>(path: string, method: StudyMutationMethod, body?: unknown): Promise<T> {
    return apiJsonKeepalive<T>(resolveBackendUrl(path), method, body)
  },
}

export async function fetchStudyArtifact<T>(ref: StudyArtifactRef): Promise<T> {
  const response = await fetch(resolveBackendUrl(ref.url), {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: ref.visibility === 'public' ? 'omit' : 'include',
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as {
      message?: string
      error?: string
    } | null
    throw new Error(
      payload?.message || payload?.error || `Artifact request failed (${response.status}).`,
    )
  }
  return response.json() as Promise<T>
}

import { resolveBackendUrl } from '@/config/env'
import type { StudyArtifactRef } from './types'

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

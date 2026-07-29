import type { QueryClient } from '@tanstack/react-query'
import { fetchStudyArtifact } from './api'
import type {
  StudyContentArtifact,
  StudyManifest,
  StudyTemplateArtifact,
} from './types'

const ARTIFACT_CACHE_LIFETIME = Number.POSITIVE_INFINITY

export function studyTemplateArtifactQueryKey(manifest?: StudyManifest) {
  const ref = manifest?.template_ref
  return [
    'study',
    'template',
    manifest?.renderer_abi || '',
    ref?.id || '',
    ref?.version || '',
  ] as const
}

export function studyContentArtifactQueryKey(manifest?: StudyManifest) {
  const ref = manifest?.content_ref
  return [
    'study',
    'content',
    manifest?.renderer_abi || '',
    manifest?.card_id || '',
    manifest?.template_id || '',
    ref?.id || '',
    ref?.version || '',
  ] as const
}

function assertArtifactIdentity(
  manifest: StudyManifest,
  artifact: {
    id: string
    version: string
    renderer_abi: string
  },
  expected: {
    id: string
    version: string
  },
  label: string,
) {
  if (artifact.id !== expected.id || artifact.version !== expected.version) {
    throw new Error(`${label} artifact identity mismatch.`)
  }
  if (
    manifest.renderer_abi
    && artifact.renderer_abi !== manifest.renderer_abi
  ) {
    throw new Error(`${label} renderer ABI mismatch.`)
  }
}

export function studyTemplateArtifactQueryOptions(manifest?: StudyManifest) {
  const ref = manifest?.template_ref
  return {
    queryKey: studyTemplateArtifactQueryKey(manifest),
    queryFn: async () => {
      if (!manifest || !ref) throw new Error('Thiếu template artifact.')
      const artifact = await fetchStudyArtifact<StudyTemplateArtifact>(ref)
      assertArtifactIdentity(manifest, artifact, ref, 'Template')
      return artifact
    },
    staleTime: ARTIFACT_CACHE_LIFETIME,
    gcTime: ARTIFACT_CACHE_LIFETIME,
  }
}

export function studyContentArtifactQueryOptions(manifest?: StudyManifest) {
  const ref = manifest?.content_ref
  return {
    queryKey: studyContentArtifactQueryKey(manifest),
    queryFn: async () => {
      if (!manifest || !ref) throw new Error('Thiếu content artifact.')
      const artifact = await fetchStudyArtifact<StudyContentArtifact>(ref)
      assertArtifactIdentity(manifest, artifact, ref, 'Content')
      return artifact
    },
    staleTime: ARTIFACT_CACHE_LIFETIME,
    gcTime: ARTIFACT_CACHE_LIFETIME,
  }
}

export async function ensureStudyManifestArtifacts(
  queryClient: QueryClient,
  manifest: StudyManifest,
) {
  if (!manifest.card_id) return

  const pending: Promise<unknown>[] = []
  if (manifest.template_ref) {
    pending.push(
      queryClient.ensureQueryData(studyTemplateArtifactQueryOptions(manifest)),
    )
  }
  if (manifest.content_ref) {
    pending.push(
      queryClient.ensureQueryData(studyContentArtifactQueryOptions(manifest)),
    )
  }
  await Promise.all(pending)
}

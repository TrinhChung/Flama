import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ensureStudyManifestArtifacts,
  studyContentArtifactQueryKey,
  studyTemplateArtifactQueryKey,
} from './queries'
import type { StudyManifest } from './types'

function manifest(overrides: Partial<StudyManifest> = {}): StudyManifest {
  return {
    schema_version: 'study-manifest.v1',
    render_contract: 'client_v1',
    renderer_abi: 'flama-client-mustache.v1',
    card_id: 'card-1',
    note_id: 'note-1',
    template_id: 'template-1',
    template_ref: {
      id: 'template-1',
      version: 'sha256-template',
      url: '/api/study/artifacts/private/cards/card-1/template/versions/sha256-template',
      visibility: 'private',
    },
    content_ref: {
      id: 'note-1',
      version: 'sha256-content',
      url: '/api/study/artifacts/private/cards/card-1/content/versions/sha256-content',
      visibility: 'private',
    },
    ...overrides,
  }
}

describe('study artifact query keys', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reuses a template across card-scoped artifact URLs', () => {
    const first = manifest()
    const second = manifest({
      card_id: 'card-2',
      note_id: 'note-2',
      template_ref: {
        ...first.template_ref!,
        url: '/api/study/artifacts/private/cards/card-2/template/versions/sha256-template',
      },
    })

    expect(studyTemplateArtifactQueryKey(first)).toEqual(
      studyTemplateArtifactQueryKey(second),
    )
  })

  it('invalidates a template when its content version changes', () => {
    const first = manifest()
    const updated = manifest({
      template_ref: {
        ...first.template_ref!,
        version: 'sha256-template-updated',
      },
    })

    expect(studyTemplateArtifactQueryKey(first)).not.toEqual(
      studyTemplateArtifactQueryKey(updated),
    )
  })

  it('keeps content artifacts isolated by card and template', () => {
    const first = manifest()
    const second = manifest({
      card_id: 'card-2',
      template_id: 'template-2',
      content_ref: {
        ...first.content_ref!,
        url: '/api/study/artifacts/private/cards/card-2/content/versions/sha256-content',
      },
    })

    expect(studyContentArtifactQueryKey(first)).not.toEqual(
      studyContentArtifactQueryKey(second),
    )
  })

  it('fetches a shared template only once across consecutive cards', async () => {
    const first = manifest({ content_ref: undefined })
    const second = manifest({
      card_id: 'card-2',
      note_id: 'note-2',
      content_ref: undefined,
      template_ref: {
        ...first.template_ref!,
        url: '/api/study/artifacts/private/cards/card-2/template/versions/sha256-template',
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        schema_version: 'study-template.v1',
        renderer_abi: 'flama-client-mustache.v1',
        id: 'template-1',
        version: 'sha256-template',
        front_source: '{{Word}}',
        back_source: '{{Meaning}}',
        front_inline_scripts: [],
        back_inline_scripts: [],
        shared_css: '',
        field_defs: [],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient()

    await ensureStudyManifestArtifacts(queryClient, first)
    await ensureStudyManifestArtifacts(queryClient, second)

    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

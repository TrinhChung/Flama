// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { adaptStudySessionToRenderPayload } from './studyRendererAdapter'
import type { StudyContentArtifact, StudyTemplateArtifact } from '../types'

function sampleTemplate(overrides: Partial<StudyTemplateArtifact> = {}): StudyTemplateArtifact {
  return {
    schema_version: 'study-template.v1',
    renderer_abi: 'flama-client-mustache.v1',
    id: 'template-1',
    version: 'sha256-template',
    front_source: '<div>{{Word}}</div>',
    back_source: '<div>{{{Meaning}}}</div>',
    front_inline_scripts: [],
    back_inline_scripts: ['<script>console.log("back script")</script>'],
    shared_css: '.card { color: blue; }',
    field_defs: [{ name: 'Word', field_type: 'text' }, { name: 'Meaning', field_type: 'markdown' }],
    ...overrides,
  }
}

function sampleContent(overrides: Partial<StudyContentArtifact> = {}): StudyContentArtifact {
  return {
    schema_version: 'study-content.v1',
    renderer_abi: 'flama-client-mustache.v1',
    id: 'note-1',
    note_id: 'note-1',
    version: 'sha256-content',
    field_values: { Word: '猫', Meaning: '**cat**' },
    render_context: { Word: '猫', Meaning: '<strong>cat</strong>' },
    media: [
      {
        id: 'asset-1',
        field_name: 'Audio',
        filename: 'neko.mp3',
        mime_type: 'audio/mpeg',
        sha256: 'sha-audio',
        proxy_url: '/media/proxy/asset-1',
      },
    ],
    ...overrides,
  }
}

describe('adaptStudySessionToRenderPayload', () => {
  it('correctly adapts front side template and content into CardRenderPayload', () => {
    const payload = adaptStudySessionToRenderPayload(sampleTemplate(), sampleContent(), 'front')

    expect(payload.html).toContain('猫')
    expect(payload.html).toContain('<style>.card { color: blue; }</style>')
    expect(payload.template_key).toBe('sha256-template:front')
    expect(payload.shell_key).toBe('sha256-template:front')
    expect(payload.has_inline_script).toBe(false)
    expect(payload.supports_live_patch).toBe(true)
    expect(payload.allowed_audio_urls).toContain('/media/proxy/asset-1')
    expect(payload.allowed_audio_asset_ids).toContain('asset-1')
  })

  it('correctly adapts back side template and content into CardRenderPayload with inline scripts', () => {
    const payload = adaptStudySessionToRenderPayload(sampleTemplate(), sampleContent(), 'back')

    expect(payload.html).toContain('<strong>cat</strong>')
    expect(payload.template_key).toBe('sha256-template:back')
    expect(payload.has_inline_script).toBe(true)
    expect(payload.supports_live_patch).toBe(false)
    expect(payload.html).toContain('<script>console.log("back script")</script>')
  })

  it('throws an error when renderer_abi mismatches between template and content', () => {
    const mismatchedContent = sampleContent({ renderer_abi: 'different-abi.v2' })

    expect(() => {
      adaptStudySessionToRenderPayload(sampleTemplate(), mismatchedContent, 'front')
    }).toThrow('Study renderer ABI mismatch.')
  })
})

// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { renderStudySide } from './clientRenderer'
import type {
  StudyContentArtifact,
  StudyTemplateArtifact,
} from '../types'

function template(overrides: Partial<StudyTemplateArtifact> = {}): StudyTemplateArtifact {
  return {
    schema_version: 'study-template.v1',
    renderer_abi: 'flama-client-mustache.v1',
    id: 'template-1',
    version: 'sha256-template',
    front_source: '<div>{{Word}}</div>',
    back_source: '<div>{{{Meaning}}}</div>',
    front_inline_scripts: [],
    back_inline_scripts: [],
    shared_css: '.card { color: red; }',
    field_defs: [],
    ...overrides,
  }
}

function content(overrides: Partial<StudyContentArtifact> = {}): StudyContentArtifact {
  return {
    schema_version: 'study-content.v1',
    renderer_abi: 'flama-client-mustache.v1',
    id: 'note-1',
    note_id: 'note-1',
    version: 'sha256-content',
    field_values: { Word: '犬', Meaning: '**dog**' },
    render_context: { Word: '犬', Meaning: '<strong>dog</strong>' },
    media: [],
    ...overrides,
  }
}

describe('renderStudySide', () => {
  it('renders Mustache context and preserves safe rich HTML', () => {
    const result = renderStudySide(template(), content(), 'back')
    expect(result.html).toContain('<strong>dog</strong>')
    expect(result.html).toContain('<style>.card { color: red; }</style>')
  })

  it('escapes normal Mustache fields', () => {
    const result = renderStudySide(
      template({ front_source: '<div>{{Word}}</div>' }),
      content({ render_context: { Word: '<img src=x onerror=alert(1)>' } }),
      'front',
    )
    expect(result.html).toContain('&lt;img')
    expect(result.html).not.toContain('<img')
  })

  it('removes content-injected scripts and unsafe media URLs', () => {
    const result = renderStudySide(
      template({ front_source: '<div>{{{Meaning}}}</div>' }),
      content({
        render_context: {
          Meaning: '<script>alert(1)</script><img src="https://evil.example/a.png">',
        },
      }),
      'front',
    )
    expect(result.html).not.toContain('<script>alert(1)</script>')
    expect(result.html).not.toContain('https://evil.example')
  })

  it('restores only server-validated template scripts inside renderer payload', () => {
    const result = renderStudySide(
      template({ front_inline_scripts: ['<script>window.cardReady = true</script>'] }),
      content(),
      'front',
    )
    expect(result.html).toContain('<script>window.cardReady = true</script>')
    expect(result.has_inline_script).toBe(true)
    expect(result.supports_live_patch).toBe(false)
  })

  it('converts linebreak tokens in text nodes and derives media allowlists', () => {
    const result = renderStudySide(
      template({ front_source: '<div>{{Word}}</div>' }),
      content({
        render_context: { Word: `a__FC_LINEBREAK_TOKEN__b` },
        media: [{
          id: 'asset-1',
          field_name: 'Audio',
          filename: 'a.mp3',
          mime_type: 'audio/mpeg',
          sha256: 'abc',
          proxy_url: '/media/proxy/asset-1',
        }],
      }),
      'front',
    )
    expect(result.html).toContain('a<br>b')
    expect(result.allowed_audio_urls).toEqual(['/media/proxy/asset-1'])
  })
})

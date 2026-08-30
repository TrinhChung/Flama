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

  it('renders custom audio HTML only with media attached to the content artifact', () => {
    const result = renderStudySide(
      template({
        back_source: (
          '<audio id="custom-audio" src="{{word_audio}}"></audio>'
          + '<button onclick="document.getElementById(\'custom-audio\').play()">🔊</button>'
        ),
      }),
      content({
        render_context: { word_audio: '/media/proxy/audio-1' },
        media: [{
          id: 'audio-1',
          field_name: 'word_audio',
          filename: 'word.mp3',
          mime_type: 'audio/mpeg',
          sha256: 'abc',
          proxy_url: '/media/proxy/audio-1',
        }],
      }),
      'back',
    )

    expect(result.html).toContain('id="custom-audio"')
    expect(result.html).toContain('src="/media/proxy/audio-1"')
    expect(result.html).toContain('>🔊</button>')
  })

  it('rejects a proxy-looking URL that is absent from the content media allowlist', () => {
    const result = renderStudySide(
      template({ front_source: '<audio src="{{audio_url}}"></audio>' }),
      content({
        render_context: { audio_url: '/media/proxy/not-attached' },
        media: [],
      }),
      'front',
    )

    expect(result.html).not.toContain('src=')
  })

  it('preserves static stroke diagram SVG images in rich HTML content', () => {
    const strokeDiagramHtml = (
      '<div class="flama-stroke-diagram" data-locale="ja">'
      + '<img src="/static/strokes/ja/52c9.svg" alt="勉" title="勉" class="stroke-svg" loading="lazy" />'
      + '<img src="/static/strokes/ja/5f37.svg" alt="強" title="強" class="stroke-svg" loading="lazy" />'
      + '</div>'
    )
    const result = renderStudySide(
      template({ back_source: '<div class="strokes">{{{StrokeDiagram}}}</div>' }),
      content({
        render_context: { StrokeDiagram: strokeDiagramHtml },
      }),
      'back',
    )

    expect(result.html).toContain('src="/static/strokes/ja/52c9.svg"')
    expect(result.html).toContain('src="/static/strokes/ja/5f37.svg"')
    expect(result.html).toContain('alt="勉"')
    expect(result.html).toContain('class="stroke-svg"')
  })

  it('preserves library stroke diagram SVG images in rich HTML content', () => {
    const strokeDiagramHtml = (
      '<div class="flama-stroke-diagram" data-locale="ja">'
      + '<img src="/media/library/stroke_ja_65e5.svg" alt="日" class="flama-stroke-char" />'
      + '</div>'
    )
    const result = renderStudySide(
      template({ back_source: '<div class="strokes">{{{StrokeDiagram}}}</div>' }),
      content({
        render_context: { StrokeDiagram: strokeDiagramHtml },
      }),
      'back',
    )

    expect(result.html).toContain('src="/media/library/stroke_ja_65e5.svg"')
    expect(result.html).toContain('alt="日"')
    expect(result.html).toContain('class="flama-stroke-char"')
  })

  it('preserves inline SVG markup in card render context', () => {
    const svgMarkup = '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" stroke="green" stroke-width="4" fill="yellow" /></svg>'
    const result = renderStudySide(
      template({ back_source: '<div class="diagram-container">{{{Diagram}}}</div>' }),
      content({
        render_context: { Diagram: svgMarkup },
      }),
      'back',
    )

    expect(result.html).toContain('<svg viewBox="0 0 100 100"')
    expect(result.html).toContain('<circle cx="50" cy="50" r="40"')
    expect(result.html).toContain('fill="yellow"')
  })
})


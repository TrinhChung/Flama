// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { renderStudySide, patchRenderContext, LINEBREAK_TOKEN } from './clientRenderer'
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

  it('removes content-injected scripts and untyped external media URLs', () => {
    const result = renderStudySide(
      template({ front_source: '<div>{{{Meaning}}}</div>' }),
      content({
        render_context: {
          Meaning: (
            '<script>alert(1)</script><a href="javascript:alert(2)">click</a>'
            + '<img src="https://tracker.example/pixel.png">'
          ),
        },
      }),
      'front',
    )
    expect(result.html).not.toContain('<script>alert(1)</script>')
    expect(result.html).not.toContain('javascript:')
    expect(result.html).not.toContain('tracker.example')
  })

  it('allows safe external URLs from typed media fields and URL helpers', () => {
    const result = renderStudySide(
      template({
        front_source: '<div>{{{Image}}}<audio controls src="{{Audio_url}}"></audio></div>',
        field_defs: [
          { name: 'Image', field_type: 'image' },
          { name: 'Audio', field_type: 'audio' },
        ],
      }),
      content({
        render_context: {
          Image: '<img src="https://example.com/a.png">',
          Image_url: 'https://example.com/a.png',
          Image_urls: ['https://example.com/a.png'],
          Audio: '<audio controls src="https://example.com/a.mp3"></audio>',
          Audio_url: 'https://example.com/a.mp3',
          Audio_urls: ['https://example.com/a.mp3'],
        },
      }),
      'front',
    )
    expect(result.html).toContain('<img src="https://example.com/a.png">')
    expect(result.html).toContain('src="https://example.com/a.mp3"')
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
    expect(result.html).toContain('onclick=')
  })

  it('preserves onclick with style.display assignment (show/hide hint)', () => {
    const result = renderStudySide(
      template({
        back_source: (
          '<button onclick="document.getElementById(\'hint\').style.display=\'block\'; this.style.display=\'none\'">Show</button>'
          + '<div id="hint" style="display:none">Hint text</div>'
        ),
      }),
      content({}),
      'back',
    )
    expect(result.html).toContain('onclick=')
    expect(result.html).toContain("style.display='block'")
  })

  it('preserves onclick with classList.toggle', () => {
    const result = renderStudySide(
      template({
        back_source: '<button onclick="document.getElementById(\'answer\').classList.toggle(\'hidden\')">Toggle</button>',
      }),
      content({}),
      'back',
    )
    expect(result.html).toContain('onclick=')
    expect(result.html).toContain('classList.toggle')
  })

  it('preserves onclick with pause() and hidden assignment', () => {
    const result = renderStudySide(
      template({
        back_source: '<button onclick="document.getElementById(\'audio1\').pause()">⏸</button>',
      }),
      content({}),
      'back',
    )
    expect(result.html).toContain('onclick=')
    expect(result.html).toContain('.pause()')
  })

  it('preserves onclick with this.textContent assignment', () => {
    const result = renderStudySide(
      template({
        back_source: '<button onclick="this.textContent=\'Done\'">Click me</button>',
      }),
      content({}),
      'back',
    )
    expect(result.html).toContain('onclick=')
  })

  it('strips unsafe onclick patterns (alert, fetch, eval)', () => {
    const unsafePatterns = [
      'alert("xss")',
      'fetch("https://evil.com")',
      'eval("code")',
      'window.location="https://evil.com"',
      'document.cookie',
    ]
    for (const pattern of unsafePatterns) {
      const result = renderStudySide(
        template({ back_source: `<button onclick="${pattern}">X</button>` }),
        content({}),
        'back',
      )
      expect(result.html).not.toContain('onclick=')
    }
  })

  it('strips onclick on non-button elements', () => {
    const result = renderStudySide(
      template({
        back_source: '<div onclick="document.getElementById(\'x\').play()">Click</div>',
      }),
      content({}),
      'back',
    )
    expect(result.html).not.toContain('onclick=')
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

  describe('patchRenderContext', () => {
    it('normalizes newlines to LINEBREAK_TOKEN and updates render_context', () => {
      const prevContext = { Word: '犬', Meaning: 'Dog' }
      const updated = patchRenderContext(prevContext, { Meaning: 'Line 1\nLine 2\r\nLine 3' })
      expect(updated.Meaning).toBe(`Line 1${LINEBREAK_TOKEN}Line 2${LINEBREAK_TOKEN}Line 3`)
      expect(updated.Word).toBe('犬')
    })

    it('extracts media urls for image and audio', () => {
      const updated = patchRenderContext({}, {
        Audio: '[sound:http://example.com/sound.mp3]',
        Image: '<img src="http://example.com/cat.jpg">',
      })
      expect(updated.Audio_url).toBe('http://example.com/sound.mp3')
      expect(updated.Audio_urls).toEqual(['http://example.com/sound.mp3'])
      expect(updated.Image_url).toBe('http://example.com/cat.jpg')
      expect(updated.Image_urls).toEqual(['http://example.com/cat.jpg'])
    })

    it('supports alias mapping like han_viet and nested objects', () => {
      const updated = patchRenderContext({}, {
        han_viet: 'KHUYỂN',
        'meta.source': 'JMdict',
      })
      expect(updated.han_viet).toBe('KHUYỂN')
      expect(updated.hanviet).toBe('KHUYỂN')
      expect((updated as any).meta?.source).toBe('JMdict')
    })

    it('allows updated render_context to be immediately rendered with new content', () => {
      const baseTemplate = template({ front_source: '<div>{{Word}}</div>', back_source: '<div>{{{Meaning}}}</div>' })
      const baseContent = content({
        field_values: { Word: '犬', Meaning: 'Original Dog' },
        render_context: { Word: '犬', Meaning: 'Original Dog' },
      })

      const initialResult = renderStudySide(baseTemplate, baseContent, 'back')
      expect(initialResult.html).toContain('Original Dog')

      const newFieldValues = { Word: '猫', Meaning: 'Updated Cat\nNew line' }
      const updatedContent = {
        ...baseContent,
        field_values: newFieldValues,
        render_context: patchRenderContext(baseContent.render_context, newFieldValues),
      }

      const updatedResult = renderStudySide(baseTemplate, updatedContent, 'back')
      expect(updatedResult.html).toContain('Updated Cat<br>New line')
      expect(updatedResult.html).not.toContain('Original Dog')
    })
  })
})


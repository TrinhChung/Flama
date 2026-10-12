// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { renderCardSide, patchRenderContext, LINEBREAK_TOKEN } from './clientRenderer'
import type {
  CardRenderContent,
  CardRenderTemplate,
} from '../model/types'

function template(overrides: Partial<CardRenderTemplate> = {}): CardRenderTemplate {
  return {
    renderer_abi: 'flama-client-mustache.v1',
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

function content(overrides: Partial<CardRenderContent> = {}): CardRenderContent {
  return {
    renderer_abi: 'flama-client-mustache.v1',
    field_values: { Word: '犬', Meaning: '**dog**' },
    render_context: { Word: '犬', Meaning: '<strong>dog</strong>' },
    media: [],
    ...overrides,
  }
}

describe('renderCardSide', () => {
  it('renders Mustache context and preserves safe rich HTML', () => {
    const result = renderCardSide(template(), content(), 'back')
    expect(result.html).toContain('<strong>dog</strong>')
    expect(result.html).toContain('<style>.card { color: red; }</style>')
  })

  it('escapes normal Mustache fields', () => {
    const result = renderCardSide(
      template({ front_source: '<div>{{Word}}</div>' }),
      content({ render_context: { Word: '<img src=x onerror=alert(1)>' } }),
      'front',
    )
    expect(result.html).toContain('&lt;img')
    expect(result.html).not.toContain('<img')
  })

  it('removes content-injected scripts and untyped external media URLs', () => {
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
      template({ front_inline_scripts: ['<script>window.cardReady = true</script>'] }),
      content(),
      'front',
    )
    expect(result.html).toContain('<script>window.cardReady = true</script>')
    expect(result.has_inline_script).toBe(true)
    expect(result.supports_live_patch).toBe(false)
  })

  it('shows the rendered front where the back has {{FrontSide}}, without front scripts', () => {
    const cardTemplate = template({
      front_source: '<div class="q">{{Word}}</div>{{FrontSide}}',
      back_source: '{{FrontSide}}<hr id="answer">{{{Meaning}}}',
      front_inline_scripts: ['<script>window.front = 1</script>'],
      back_inline_scripts: ['<script>window.back = 1</script>'],
    })
    const back = renderCardSide(cardTemplate, content(), 'back')
    expect(back.html).toContain('<div class="q">犬</div><hr id="answer"><strong>dog</strong><script>window.back = 1</script>')
    expect(back.html).not.toContain('window.front')
    expect(back.html).not.toContain('flama-front-side')
    const front = renderCardSide(cardTemplate, content(), 'front')
    expect(front.html).toContain('<div class="q">犬</div><script>window.front = 1</script>')
    expect(front.html).not.toContain('flama-front-side')
  })

  it('accepts every {{FrontSide}} spelling and sections while field text cannot forge it', () => {
    for (const back of [
      '{{{FrontSide}}}|{{Meaning}}',
      '{{ FrontSide }}|{{Meaning}}',
      '{{&FrontSide}}|{{Meaning}}',
      '{{&amp;FrontSide}}|{{Meaning}}',
      '{{#Meaning}}{{FrontSide}}{{/Meaning}}|{{Meaning}}',
    ]) {
      const result = renderCardSide(
        template({ front_source: '<b>{{Word}}</b>', back_source: back }),
        content({ render_context: { Word: '<flama-front-side></flama-front-side>', Meaning: 'dog' } }),
        'back',
      )
      expect(result.html, back).toContain('<b>&lt;flama-front-side&gt;&lt;/flama-front-side&gt;</b>|dog')
    }
  })

  it('keeps front media URLs allowed inside {{FrontSide}} on the back', () => {
    const result = renderCardSide(
      template({
        front_source: '<audio controls src="{{Audio_url}}"></audio>',
        back_source: '{{FrontSide}}<hr>{{Word}}',
        field_defs: [{ name: 'Audio', field_type: 'audio' }],
      }),
      content({
        render_context: {
          Word: '犬',
          Audio: '<audio controls src="https://example.com/a.mp3"></audio>',
          Audio_url: 'https://example.com/a.mp3',
          Audio_urls: ['https://example.com/a.mp3'],
        },
      }),
      'back',
    )
    expect(result.html).toContain('src="https://example.com/a.mp3"')
    expect(result.allowed_media_urls).toContain('https://example.com/a.mp3')
  })

  it('keeps a template answer box and gives its hidden answers one line each', () => {
    const result = renderCardSide(
      template({
        front_source: '<label for="guess">Đáp án</label><input id="guess" type="text" autocomplete="off"><div id="answers" hidden>{{Answer}}</div>',
        front_inline_scripts: ['<script>document.getElementById("guess").focus()</script>'],
      }),
      content({ render_context: { Answer: 'tối thiểu__FC_LINEBREAK_TOKEN__ít nhất' } }),
      'front',
    )
    expect(result.html).toContain('<label for="guess">Đáp án</label><input id="guess" type="text" autocomplete="off">')
    expect(result.html).toContain('<div id="answers" hidden="">tối thiểu<br>ít nhất</div>')
    expect(result.html).toContain('<script>document.getElementById("guess").focus()</script>')
  })

  it('iterates a stored array as is, printing {{field}} like the server', () => {
    const result = renderCardSide(
      template({
        front_source: '{{#Meaning}}<li>{{.}}</li>{{/Meaning}}|{{Meaning}}|{{#Pairs}}[{{#.}}<i>{{.}}</i>{{/.}}]{{/Pairs}}',
        field_defs: [{ name: 'Meaning', field_type: 'array' }, { name: 'Pairs', field_type: 'array' }],
      }),
      content({ render_context: { Meaning: ['ăn', '<b>dùng</b>'], Pairs: [['a', 'b'], ['c']] } }),
      'front',
    )
    expect(result.html).toContain('<li>ăn</li><li>&lt;b&gt;dùng&lt;/b&gt;</li>|ăn,&lt;b&gt;dùng&lt;/b&gt;|[<i>a</i><i>b</i>][<i>c</i>]')
  })

  it('converts linebreak tokens in text nodes and derives media allowlists', () => {
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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
      const result = renderCardSide(
        template({ back_source: `<button onclick="${pattern}">X</button>` }),
        content({}),
        'back',
      )
      expect(result.html).not.toContain('onclick=')
    }
  })

  it('strips onclick on non-button elements', () => {
    const result = renderCardSide(
      template({
        back_source: '<div onclick="document.getElementById(\'x\').play()">Click</div>',
      }),
      content({}),
      'back',
    )
    expect(result.html).not.toContain('onclick=')
  })

  it('rejects a proxy-looking URL that is absent from the content media allowlist', () => {
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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
    const result = renderCardSide(
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

    it('keeps a stored array as the same list and older text arrays on the text path', () => {
      const pairs = [['a', 'b'], ['c']]
      const updated = patchRenderContext({}, { Pairs: pairs, Meaning: 'ăn\ndùng bữa' }, [
        { name: 'Pairs', field_type: 'array' },
        { name: 'Meaning', field_type: 'array' },
      ])
      expect(updated.Pairs).toBe(pairs)
      expect(updated.Meaning).toBe(`ăn${LINEBREAK_TOKEN}dùng bữa`)
      expect(Object.keys(updated).sort()).toEqual(['Meaning', 'Pairs'])
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

    it('generates rich media HTML tags for audio and image fields rather than plain strings', () => {
      const updated = patchRenderContext({}, {
        Audio: 'https://example.com/sound.mp3',
        Image: 'https://example.com/cat.jpg',
      })
      expect(updated.Audio).toContain('<audio controls')
      expect(updated.Audio).toContain('class="flama-media-audio"')
      expect(updated.Audio).toContain('src="https://example.com/sound.mp3"')
      expect(updated.Audio).not.toBe('https://example.com/sound.mp3')

      expect(updated.Image).toContain('<img')
      expect(updated.Image).toContain('class="flama-media-image"')
      expect(updated.Image).toContain('src="https://example.com/cat.jpg"')
      expect(updated.Image).not.toBe('https://example.com/cat.jpg')
    })

    it('renders multi-value media URLs into a gallery div', () => {
      const updated = patchRenderContext({}, {
        Image: 'https://example.com/1.png\nhttps://example.com/2.png',
      }, [{ name: 'Image', field_type: 'image' }])
      expect(updated.Image).toContain('<div class="flama-media-gallery">')
      expect(updated.Image_urls).toEqual(['https://example.com/1.png', 'https://example.com/2.png'])
    })

    it('auto-heals corrupted raw media strings upon renderCardSide', () => {
      const baseTemplate = template({
        front_source: '<div>{{{Audio}}}</div>',
        field_defs: [{ name: 'Audio', field_type: 'audio' }],
      })
      const baseContent = content({
        render_context: {
          Audio: 'https://example.com/voice.mp3',
        },
      })
      const result = renderCardSide(baseTemplate, baseContent, 'front')
      expect(result.html).toContain('<audio controls')
      expect(result.html).toContain('src="https://example.com/voice.mp3"')
      expect(result.allowed_audio_urls).toContain('https://example.com/voice.mp3')
    })

    it('supports nested dotted object mapping', () => {
      const updated = patchRenderContext({}, {
        'meta.source': 'JMdict',
      })
      expect((updated as any).meta?.source).toBe('JMdict')
    })

    it('allows updated render_context to be immediately rendered with new content', () => {
      const baseTemplate = template({ front_source: '<div>{{Word}}</div>', back_source: '<div>{{{Meaning}}}</div>' })
      const baseContent = content({
        field_values: { Word: '犬', Meaning: 'Original Dog' },
        render_context: { Word: '犬', Meaning: 'Original Dog' },
      })

      const initialResult = renderCardSide(baseTemplate, baseContent, 'back')
      expect(initialResult.html).toContain('Original Dog')

      const newFieldValues = { Word: '猫', Meaning: 'Updated Cat\nNew line' }
      const updatedContent = {
        ...baseContent,
        field_values: newFieldValues,
        render_context: patchRenderContext(baseContent.render_context, newFieldValues),
      }

      const updatedResult = renderCardSide(baseTemplate, updatedContent, 'back')
      expect(updatedResult.html).toContain('Updated Cat<br>New line')
      expect(updatedResult.html).not.toContain('Original Dog')
    })

    it('preserves arbitrary inert custom attributes while stripping dangerous handlers and capabilities', () => {
      const testTemplate = template({
        front_source: '<div auto-split data-auto-split my-marker="custom-1" foo="bar" onerror="alert(1)" onmouseover="evil()" class="card-item">{{Word}}</div>',
        back_source: '<div my-custom-attr="hello" action="http://evil.com" style="color: blue; background: url(http://evil.com)">{{Meaning}}</div>',
      })
      const testContent = content({
        render_context: {
          Word: 'A$B$C',
          Meaning: 'X$Y',
        },
      })

      const front = renderCardSide(testTemplate, testContent, 'front')
      expect(front.html).toContain('auto-split')
      expect(front.html).toContain('data-auto-split')
      expect(front.html).toContain('my-marker="custom-1"')
      expect(front.html).toContain('foo="bar"')
      expect(front.html).toContain('class="card-item"')
      expect(front.html).not.toContain('onerror')
      expect(front.html).not.toContain('onmouseover')

      const back = renderCardSide(testTemplate, testContent, 'back')
      expect(back.html).toContain('my-custom-attr="hello"')
      expect(back.html).not.toContain('action')
      expect(back.html).not.toContain('background: url')
    })

    it('does not leak un-substituted Mustache media placeholders into allowed_media_urls or CSP', () => {
      const testTemplate = template({
        front_source: '<div><audio controls src="{{{word_audio_url}}}"></audio></div>',
      })
      const testContent = content({
        render_context: {},
      })

      const result = renderCardSide(testTemplate, testContent, 'front')
      expect(result.allowed_media_urls).not.toEqual(
        expect.arrayContaining([expect.stringContaining('word_audio_url')]),
      )
      expect(result.allowed_audio_urls).not.toEqual(
        expect.arrayContaining([expect.stringContaining('word_audio_url')]),
      )
    })
  })
})

import { describe, it, expect } from 'vitest'
import {
  ankiHtmlToPlainText,
  convertFuriganaToRuby,
  extractAudioReferences,
  extractImageReferences,
  normalizeAnkiTextEntities,
  replaceMediaReferences,
  sanitizeAnkiHtml,
} from './ankiHtmlSanitizer'

describe('ankiHtmlSanitizer', () => {
  it('converts bracket furigana to ruby HTML', () => {
    const raw = '私[わたし]は漢字[かんじ]を勉強[べんきょう]します。'
    const result = convertFuriganaToRuby(raw)
    expect(result).toContain('<ruby>私<rt>わたし</rt></ruby>')
    expect(result).toContain('<ruby>漢字<rt>かんじ</rt></ruby>')
  })

  it('strips script tags and malicious event handlers', () => {
    const malicious = '<div>Hello <script>alert("xss")</script><img src="x" onerror="alert(1)" onclick="steal()"></div>'
    const clean = sanitizeAnkiHtml(malicious)
    expect(clean).not.toContain('<script>')
    expect(clean).not.toContain('onerror=')
    expect(clean).not.toContain('onclick=')
    expect(clean).toContain('<div>Hello ')
  })

  it('normalizes Anki apostrophe entities without decoding arbitrary markup', () => {
    const raw = 'Open: &#x27;from...to...&#x27;; &#39;position&#39;; &apos;vacancy&apos; &lt;script&gt;'

    expect(normalizeAnkiTextEntities(raw)).toBe(
      "Open: 'from...to...'; 'position'; 'vacancy' &lt;script&gt;"
    )
    expect(sanitizeAnkiHtml(raw)).toContain("'from...to...'")
    expect(sanitizeAnkiHtml(raw)).toContain('&lt;script&gt;')
  })

  it('converts Anki line breaks and entities for a plain-text target field', () => {
    expect(ankiHtmlToPlainText('Vた + 甲斐がある<br>Vた + 甲斐があった')).toBe(
      'Vた + 甲斐がある\nVた + 甲斐があった',
    )
    expect(ankiHtmlToPlainText('せっかく + Vた<br>&nbsp; &nbsp;Vてきた + のに')).toBe(
      'せっかく + Vた\nVてきた + のに',
    )
  })

  it('extracts image references without path traversal', () => {
    const html = '<p><img src="test1.png"> <img src="../test2.jpg"> <img src="https://example.com/test3.gif"></p>'
    const images = extractImageReferences(html)
    expect(images).toContain('test1.png')
    expect(images).not.toContain('test2.jpg')
    expect(images).not.toContain('test3.gif')
  })

  it('extracts audio references from [sound:] tags and <audio>', () => {
    const html = '<div>Word [sound:japan_word.mp3] <audio src="sample.wav"></audio></div>'
    const audios = extractAudioReferences(html)
    expect(audios).toContain('japan_word.mp3')
    expect(audios).toContain('sample.wav')
  })

  it('replaces local media references with Flama media URLs', () => {
    const html = '<div>[sound:word.mp3] <img src="pic.png"></div>'
    const mediaMap = {
      'word.mp3': { mediaId: 'media_123', url: 'https://flama.connect/media/media_123' },
      'pic.png': { mediaId: 'media_456', url: 'https://flama.connect/media/media_456' },
    }
    const result = replaceMediaReferences(html, mediaMap)
    expect(result).toContain('https://flama.connect/media/media_123')
    expect(result).toContain('https://flama.connect/media/media_456')
  })
})

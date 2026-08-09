/**
 * HTML Sanitizer & Anki Furigana / Media Extractor
 */

const PATH_TRAVERSAL = /(\.\.|\/|\\|:)/

export function convertFuriganaToRuby(text: string): string {
  if (!text || typeof text !== 'string') return ''

  // 1. Convert space-prefixed furigana (e.g., ' kanji[furigana]')
  let result = text.replace(/(^|\s)([^[\s<>]+)\[(?!sound:)([^\]]+)\]/g, (_match, space, kanji, furigana) => {
    return `${space}<ruby>${kanji}<rt>${furigana}</rt></ruby>`
  })

  // 2. Convert Kanji characters without leading space (e.g. は漢字[かんじ] -> は<ruby>漢字<rt>かんじ</rt></ruby>)
  result = result.replace(/([\u4e00-\u9faf\u3400-\u4dbf\uF900-\uFAFF\u3005]+)\[(?!sound:)([^\]]+)\]/g, (_match, kanji, furigana) => {
    return `<ruby>${kanji}<rt>${furigana}</rt></ruby>`
  })

  return result
}

export function sanitizeAnkiHtml(html: string): string {
  if (!html || typeof html !== 'string') return ''

  let clean = html

  // Remove script tags and content
  clean = clean.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')

  // Remove event handlers like onclick="...", onerror="..."
  clean = clean.replace(/\s+on[a-z]+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')

  // Remove javascript: URLs
  clean = clean.replace(/href\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, 'href="#"')
  clean = clean.replace(/src\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, 'src=""')

  // Convert bracket furigana to ruby HTML
  clean = convertFuriganaToRuby(clean)

  return clean
}

export function extractImageReferences(html: string): string[] {
  if (!html || typeof html !== 'string') return []
  const imgRegex = /<img[^>]+src=["']?([^"'>\s]+)["']?[^>]*>/gi
  const images: string[] = []
  let match: RegExpExecArray | null

  while ((match = imgRegex.exec(html)) !== null) {
    const src = match[1]?.trim()
    if (src && !src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('data:')) {
      if (!PATH_TRAVERSAL.test(src)) {
        const filename = decodeURIComponent(src)
        if (filename && !images.includes(filename)) {
          images.push(filename)
        }
      }
    }
  }
  return images
}

export function extractAudioReferences(html: string): string[] {
  if (!html || typeof html !== 'string') return []
  const audioFiles: string[] = []

  // Extract [sound:filename.mp3]
  const soundBracketRegex = /\[sound:([^\]]+)\]/gi
  let match: RegExpExecArray | null

  while ((match = soundBracketRegex.exec(html)) !== null) {
    const raw = match[1]?.trim() || ''
    if (raw && !PATH_TRAVERSAL.test(raw)) {
      const filename = decodeURIComponent(raw)
      if (filename && !audioFiles.includes(filename)) {
        audioFiles.push(filename)
      }
    }
  }

  // Extract <audio src="filename.mp3">
  const audioTagRegex = /<audio[^>]+src=["']?([^"'>\s]+)["']?[^>]*>/gi
  while ((match = audioTagRegex.exec(html)) !== null) {
    const src = match[1]?.trim()
    if (src && !src.startsWith('http://') && !src.startsWith('https://') && !src.startsWith('data:')) {
      if (!PATH_TRAVERSAL.test(src)) {
        const filename = decodeURIComponent(src)
        if (filename && !audioFiles.includes(filename)) {
          audioFiles.push(filename)
        }
      }
    }
  }

  return audioFiles
}

export function replaceMediaReferences(
  html: string,
  mediaMap: Record<string, { mediaId: string; url: string }>
): string {
  if (!html || typeof html !== 'string') return ''

  let result = sanitizeAnkiHtml(html)

  // Replace [sound:filename.mp3] with <audio controls src="url"></audio>
  result = result.replace(/\[sound:([^\]]+)\]/gi, (match, rawFilename) => {
    const filename = decodeURIComponent(rawFilename.trim())
    const media = mediaMap[filename]
    if (media) {
      return `<audio controls class="flama-audio" src="${media.url}"></audio>`
    }
    return match
  })

  // Replace <img src="filename"> src attribute
  result = result.replace(/<img([^>]+)src=["']?([^"'>\s]+)["']?([^>]*)>/gi, (match, pre, src, post) => {
    const filename = decodeURIComponent(src.split(/[/\\]/).pop() || '')
    const media = mediaMap[filename]
    if (media) {
      return `<img${pre}src="${media.url}"${post}>`
    }
    return match
  })

  return result
}

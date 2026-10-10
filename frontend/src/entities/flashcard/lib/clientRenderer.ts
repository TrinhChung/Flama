import DOMPurify from 'dompurify'
import Mustache from 'mustache'
import type {
  RendererSidePayload,
  CardRenderContent,
  CardRenderTemplate,
} from '../model/types'

export const LINEBREAK_TOKEN = '__FC_LINEBREAK_TOKEN__'

export function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

export function renderMediaHtml(
  fieldKind: 'audio' | 'image' | 'diagram' | string,
  fieldName: string,
  rawValue: string,
  mediaLookup?: Array<{ id: string; filename?: string; proxy_url?: string }> | Map<string, string>,
): { html: string; urls: string[] } {
  const trimmed = rawValue.trim()
  if (!trimmed) {
    return { html: '', urls: [] }
  }

  // If already HTML markup (e.g. from backend pre-rendered context), preserve and extract URLs
  if (
    trimmed.startsWith('<audio') ||
    trimmed.startsWith('<img') ||
    trimmed.startsWith('<div class="flama-media-gallery"')
  ) {
    const urls: string[] = []
    const srcRegex = /\bsrc=["']([^"']+)["']/g
    let match: RegExpExecArray | null
    while ((match = srcRegex.exec(trimmed)) !== null) {
      if (match[1]) urls.push(match[1])
    }
    return { html: trimmed, urls }
  }

  // Build asset lookup if provided
  const filenameMap = new Map<string, { id: string; proxy_url: string }>()
  if (Array.isArray(mediaLookup)) {
    for (const item of mediaLookup) {
      if (item && item.proxy_url) {
        if (item.filename) {
          filenameMap.set(item.filename.toLowerCase(), { id: item.id, proxy_url: item.proxy_url })
        }
        if (item.id) {
          filenameMap.set(item.id.toLowerCase(), { id: item.id, proxy_url: item.proxy_url })
        }
      }
    }
  } else if (mediaLookup instanceof Map) {
    for (const [key, val] of mediaLookup.entries()) {
      filenameMap.set(key.toLowerCase(), { id: key, proxy_url: val })
    }
  }

  const lines = trimmed
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)

  const urls: string[] = []
  const fragments: string[] = []
  const escapedField = escapeHtml(fieldName)

  for (const line of lines) {
    let candidate = line
    const soundMatch = candidate.match(/^\[sound:([^\]]+)\]$/)
    if (soundMatch && soundMatch[1]) {
      candidate = soundMatch[1].trim()
    }
    if (!candidate) continue

    let resolvedUrl = candidate
    let assetId: string | null = null

    const matchedAsset = filenameMap.get(candidate.toLowerCase())
    if (matchedAsset) {
      resolvedUrl = matchedAsset.proxy_url
      assetId = matchedAsset.id
    } else {
      const proxyMatch = candidate.match(/^\/media\/proxy\/([A-Za-z0-9][A-Za-z0-9_-]{0,127})$/)
      if (proxyMatch && proxyMatch[1]) {
        assetId = proxyMatch[1]
      }
    }

    urls.push(resolvedUrl)
    const escapedUrl = escapeHtml(resolvedUrl)
    const assetAttr = assetId ? ` data-flama-media-asset-id="${escapeHtml(assetId)}"` : ''

    const isAudio = fieldKind === 'audio'
    if (isAudio) {
      fragments.push(
        `<audio controls data-flama-media-field="${escapedField}" data-flama-media-kind="audio" class="flama-media-audio"${assetAttr} src="${escapedUrl}"></audio>`,
      )
    } else {
      const isSvg = (
        candidate.toLowerCase().endsWith('.svg')
        || resolvedUrl.toLowerCase().endsWith('.svg')
        || candidate.includes('image/svg+xml')
        || resolvedUrl.includes('image/svg+xml')
      )
      const kindAttr = isSvg ? 'svg' : (fieldKind === 'diagram' ? 'diagram' : 'image')
      const svgAttr = isSvg ? ' data-flama-is-svg="true"' : ''
      const classAttr = isSvg ? 'flama-media-image flama-svg-image' : 'flama-media-image'
      fragments.push(
        `<img data-flama-media-field="${escapedField}" data-flama-media-kind="${kindAttr}"${svgAttr} class="${classAttr}"${assetAttr} src="${escapedUrl}" alt="${escapedField}">`,
      )
    }
  }

  let html = ''
  if (fragments.length === 1) {
    html = fragments[0]
  } else if (fragments.length > 1) {
    html = `<div class="flama-media-gallery">${fragments.join('')}</div>`
  }

  return { html, urls }
}

export function patchRenderContext(
  existingRenderContext: Record<string, unknown>,
  newFieldValues: Record<string, string>,
  fieldDefs?: Array<{ name: string; field_type?: string }>,
  mediaLookup?: Array<{ id: string; filename?: string; proxy_url?: string; mime_type?: string }>,
): Record<string, unknown> {
  const next: Record<string, unknown> = { ...existingRenderContext }
  const fieldTypeMap = new Map<string, string>()
  if (fieldDefs) {
    for (const def of fieldDefs) {
      if (def?.name) {
        fieldTypeMap.set(def.name, String(def.field_type || '').toLowerCase())
      }
    }
  }

  for (const [key, rawValue] of Object.entries(newFieldValues)) {
    const stringValue = rawValue === null || rawValue === undefined ? '' : String(rawValue)
    const fieldType = fieldTypeMap.get(key) || 'text'
    const lowerKey = key.toLowerCase()
    const isAudio = (
      fieldType === 'audio' ||
      lowerKey === 'audio' ||
      lowerKey === 'sound' ||
      lowerKey === 'voice' ||
      lowerKey.endsWith('_audio') ||
      lowerKey.endsWith(' audio') ||
      lowerKey.endsWith('_sound') ||
      lowerKey.endsWith(' sound') ||
      stringValue.trim().startsWith('[sound:')
    )
    const isImage = (
      fieldType === 'image' ||
      fieldType === 'diagram' ||
      lowerKey === 'image' ||
      lowerKey === 'picture' ||
      lowerKey === 'photo' ||
      lowerKey === 'diagram' ||
      lowerKey === 'illustration' ||
      lowerKey.endsWith('_image') ||
      lowerKey.endsWith(' image') ||
      lowerKey.endsWith('_photo') ||
      lowerKey.endsWith(' photo')
    )
    const isMedia = isAudio || isImage

    if (isMedia) {
      const trimmed = stringValue.trim()
      if (!trimmed) {
        next[key] = ''
        next[`${key}_url`] = ''
        next[`${key}_urls`] = []
      } else {
        const kind = isAudio ? 'audio' : (fieldType === 'diagram' ? 'diagram' : 'image')
        const { html, urls } = renderMediaHtml(kind, key, trimmed, mediaLookup)
        next[key] = html
        next[`${key}_url`] = urls[0] || ''
        next[`${key}_urls`] = urls
      }
    } else {
      const normalized = stringValue
        .replace(/\r\n/g, '\n')
        .replace(/\r/g, '\n')
        .replace(/\\n/g, LINEBREAK_TOKEN)
        .replace(/\n/g, LINEBREAK_TOKEN)
      next[key] = normalized
      if (key === 'hanviet') {
        next['han_viet'] = normalized
      } else if (key === 'han_viet') {
        next['hanviet'] = normalized
      }
    }

    if (key.includes('.')) {
      const parts = key.split('.')
      let curr: Record<string, unknown> = next
      for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i]
        if (!curr[part] || typeof curr[part] !== 'object' || Array.isArray(curr[part])) {
          curr[part] = {}
        }
        curr = curr[part] as Record<string, unknown>
      }
      curr[parts[parts.length - 1]] = next[key]
    }
  }

  return next
}

const PROXY_MEDIA_RE = /^\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/
const LIBRARY_MEDIA_RE = /^\/media\/library\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}(?:\.(?:svg|png|jpe?g|webp|gif|mp3|wav|ogg|webm))?$/i
const STATIC_STROKE_RE = /^\/static\/strokes\/[a-zA-Z0-9_-]+\/[a-fA-F0-9]+\.svg$/

const SAFE_ID = String.raw`[A-Za-z0-9_-]+`
const TARGET_RE_SRC = String.raw`(?:document\.getElementById\(\s*['"]${SAFE_ID}['"]\s*\)|this)`

const SAFE_METHOD_RE = new RegExp(
  String.raw`^${TARGET_RE_SRC}\.(?:play|pause|load|click|focus|blur|remove)\(\)$`,
)
const SAFE_STYLE_RE = new RegExp(
  String.raw`^${TARGET_RE_SRC}\.style\.[a-zA-Z]+\s*=\s*'[^']{0,50}'$`,
)
const SAFE_CLASSLIST_RE = new RegExp(
  String.raw`^${TARGET_RE_SRC}\.classList\.(?:add|remove|toggle)\(\s*'[A-Za-z0-9_-]+'\s*\)$`,
)
const SAFE_HIDDEN_RE = new RegExp(
  String.raw`^${TARGET_RE_SRC}\.hidden\s*=\s*(?:true|false)$`,
)
const SAFE_TEXTCONTENT_RE = new RegExp(
  String.raw`^${TARGET_RE_SRC}\.textContent\s*=\s*'[^']{0,100}'$`,
)

const SAFE_ONCLICK_PATTERNS = [
  SAFE_METHOD_RE,
  SAFE_STYLE_RE,
  SAFE_CLASSLIST_RE,
  SAFE_HIDDEN_RE,
  SAFE_TEXTCONTENT_RE,
]

function isSafeOnclickValue(value: string): boolean {
  const statements = value.split(';').map((s) => s.trim()).filter(Boolean)
  if (statements.length === 0 || statements.length > 10) return false
  return statements.every((stmt) => SAFE_ONCLICK_PATTERNS.some((re) => re.test(stmt)))
}

function isApprovedMediaUrl(value: string): boolean {
  if (PROXY_MEDIA_RE.test(value) || LIBRARY_MEDIA_RE.test(value) || STATIC_STROKE_RE.test(value)) {
    return true
  }
  try {
    const parsed = new URL(value, window.location.origin)
    if (parsed.protocol === 'https:' && value.startsWith('https://')) return true
    return parsed.protocol === 'http:'
      && ['localhost', '127.0.0.1', '::1'].includes(parsed.hostname)
  } catch {
    return false
  }
}

function collectMediaUrlsFromMarkup(rawHtml: string): { media: string[]; audio: string[] } {
  const template = document.createElement('template')
  template.innerHTML = rawHtml
  const media = new Set<string>()
  const audio = new Set<string>()
  template.content.querySelectorAll('img[src], audio[src], video[src], video[poster], source[src]').forEach((node) => {
    const attr = node.hasAttribute('src') ? 'src' : 'poster'
    const value = String(node.getAttribute(attr) || '').trim()
    if (!value || value.includes('{{') || value.includes('}}')) return
    if (PROXY_MEDIA_RE.test(value) || !isApprovedMediaUrl(value)) return
    media.add(value)
    if (node.nodeName.toLowerCase() === 'audio') audio.add(value)
    if (node.nodeName.toLowerCase() === 'source') {
      const type = String(node.getAttribute('type') || '').toLowerCase()
      if (type.startsWith('audio/')) audio.add(value)
    }
  })
  return { media: [...media], audio: [...audio] }
}

function collectTrustedMediaUrls(
  template: CardRenderTemplate,
  content: CardRenderContent,
  source: string,
): { media: string[]; audio: string[] } {
  const templateUrls = collectMediaUrlsFromMarkup(source)
  const media = new Set(templateUrls.media)
  const audio = new Set(templateUrls.audio)

  const addUrl = (rawValue: unknown, isAudio: boolean) => {
    const value = typeof rawValue === 'string' ? rawValue.trim() : ''
    if (!value || PROXY_MEDIA_RE.test(value) || !isApprovedMediaUrl(value)) return
    media.add(value)
    if (isAudio) audio.add(value)
  }

  template.field_defs.forEach((field) => {
    const fieldType = String(field.field_type || '').toLowerCase()
    const fieldName = String(field.name || '')
    const lowerName = fieldName.toLowerCase()
    const isAudio = (
      fieldType === 'audio' ||
      lowerName === 'audio' ||
      lowerName === 'sound' ||
      lowerName === 'voice' ||
      lowerName.endsWith('_audio') ||
      lowerName.endsWith(' audio') ||
      lowerName.endsWith('_sound') ||
      lowerName.endsWith(' sound')
    )
    const isImage = (
      fieldType === 'image' ||
      fieldType === 'diagram' ||
      lowerName === 'image' ||
      lowerName === 'picture' ||
      lowerName === 'photo' ||
      lowerName === 'diagram' ||
      lowerName === 'illustration' ||
      lowerName.endsWith('_image') ||
      lowerName.endsWith(' image') ||
      lowerName.endsWith('_photo') ||
      lowerName.endsWith(' photo')
    )
    if (!isAudio && !isImage) return

    const urlList = content.render_context[`${fieldName}_urls`]
    if (Array.isArray(urlList)) {
      urlList.forEach((value) => addUrl(value, isAudio))
    }
    addUrl(content.render_context[`${fieldName}_url`], isAudio)

    const renderedField = content.render_context[fieldName]
    if (typeof renderedField === 'string') {
      addUrl(renderedField, isAudio)
      const fieldMarkupUrls = collectMediaUrlsFromMarkup(renderedField)
      fieldMarkupUrls.media.forEach((value) => addUrl(value, isAudio))
    }
  })

  return { media: [...media], audio: [...audio] }
}

const ALLOWED_TAGS = [
  'div', 'span', 'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'u', 's', 'mark',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'pre',
  'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'img', 'audio', 'video',
  'source', 'button', 'ruby', 'rt', 'rp', 'a', 'style',
  'svg', 'g', 'path', 'line', 'circle', 'rect', 'ellipse', 'polyline', 'polygon', 'text', 'tspan',
  // A template's own answer box (server TEMPLATE_HTML_TAGS).
  'input', 'label',
]

const ALLOWED_ATTR = [
  'class', 'id', 'style', 'alt', 'title', 'role', 'dir', 'controls', 'loop',
  'muted', 'playsinline', 'autoplay', 'preload', 'poster', 'width', 'height',
  'colspan', 'rowspan', 'src', 'href', 'onclick', 'loading',
  'viewBox', 'viewbox', 'xmlns', 'd', 'fill', 'stroke', 'stroke-width',
  'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset',
  'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
  'transform', 'points', 'opacity', 'font-size', 'font-family', 'text-anchor',
]

const CAPABILITY_ATTRS = new Set([
  'src', 'href', 'poster', 'action', 'formaction', 'background',
  'cite', 'codebase', 'manifest', 'srcdoc',
])

const SAFE_INERT_ATTR_NAME_RE = /^[a-zA-Z_][a-zA-Z0-9_:-]*$/

function sanitizeRenderedMarkup(rawHtml: string, allowedMediaUrls: Set<string>): string {
  DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
    const attrName = data.attrName.toLowerCase()
    const attrValue = String(data.attrValue || '').trim()
    if (attrName.startsWith('on')) {
      const isSafe = (
        attrName === 'onclick'
        && node.nodeName.toLowerCase() === 'button'
        && isSafeOnclickValue(attrValue)
      )
      data.keepAttr = isSafe
      if (!isSafe) {
        data.forceKeepAttr = false
      }
      return
    }
    if (attrName === 'style') {
      if (/(?:@import|url\s*\(|expression\s*\()/i.test(attrValue)) {
        data.keepAttr = false
        data.forceKeepAttr = false
      }
      return
    }
    if (CAPABILITY_ATTRS.has(attrName)) {
      if (attrName === 'src' || attrName === 'href' || attrName === 'poster') {
        const tag = node.nodeName.toLowerCase()
        const isMediaTag = tag === 'img' || tag === 'audio' || tag === 'video' || tag === 'source'
        const isAllowed = (
          (PROXY_MEDIA_RE.test(attrValue) && allowedMediaUrls.has(attrValue))
          || LIBRARY_MEDIA_RE.test(attrValue)
          || STATIC_STROKE_RE.test(attrValue)
          || (attrName === 'href' && attrValue.startsWith('https://'))
          || (isMediaTag && (attrName === 'src' || attrName === 'poster')
              && allowedMediaUrls.has(attrValue) && isApprovedMediaUrl(attrValue))
        )
        data.keepAttr = isAllowed
        if (!isAllowed) {
          data.forceKeepAttr = false
        }
      } else {
        data.keepAttr = false
        data.forceKeepAttr = false
      }
      return
    }
    if (SAFE_INERT_ATTR_NAME_RE.test(attrName)) {
      data.forceKeepAttr = true
      data.keepAttr = true
    }
  })
  try {
    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS,
      ALLOWED_ATTR,
      ADD_ATTR: ['onclick'],
      ALLOW_ARIA_ATTR: true,
      ALLOW_DATA_ATTR: true,
      USE_PROFILES: { html: true, svg: true, svgFilters: true },
    })
  } finally {
    DOMPurify.removeAllHooks()
  }
}

function restoreLineBreaks(safeHtml: string): string {
  if (!safeHtml.includes(LINEBREAK_TOKEN)) return safeHtml
  const template = document.createElement('template')
  template.innerHTML = safeHtml
  const walker = document.createTreeWalker(template.content, NodeFilter.SHOW_TEXT)
  const textNodes: Text[] = []
  let current = walker.nextNode()
  while (current) {
    if (current.nodeValue?.includes(LINEBREAK_TOKEN)) {
      textNodes.push(current as Text)
    }
    current = walker.nextNode()
  }
  textNodes.forEach((textNode) => {
    const parts = String(textNode.nodeValue || '').split(LINEBREAK_TOKEN)
    const fragment = document.createDocumentFragment()
    parts.forEach((part, index) => {
      if (index > 0) fragment.appendChild(document.createElement('br'))
      fragment.appendChild(document.createTextNode(part))
    })
    textNode.replaceWith(fragment)
  })
  return template.innerHTML
}

function safeCss(css: string): string {
  return String(css || '')
    .replace(/<\/style/gi, '')
    .replace(/@import[^;]+;?/gi, '')
    .replace(/url\s*\(/gi, 'blocked-url(')
    .replace(/expression\s*\(/gi, 'blocked-expression(')
}

export function renderCardSide(
  template: CardRenderTemplate,
  content: CardRenderContent,
  side: 'front' | 'back',
): RendererSidePayload {
  if (template.renderer_abi !== content.renderer_abi) {
    throw new Error('Study renderer ABI mismatch.')
  }
  const source = side === 'front' ? template.front_source : template.back_source
  const inlineScripts = (
    side === 'front'
      ? template.front_inline_scripts
      : template.back_inline_scripts
  )

  // Auto-heal render_context if any media fields were stored as raw text/URLs
  const renderContext = { ...content.render_context }
  for (const field of template.field_defs) {
    const fieldType = String(field.field_type || '').toLowerCase()
    const fieldName = String(field.name || '')
    const lowerName = fieldName.toLowerCase()
    const isAudio = (
      fieldType === 'audio' ||
      lowerName === 'audio' ||
      lowerName === 'sound' ||
      lowerName === 'voice' ||
      lowerName.endsWith('_audio') ||
      lowerName.endsWith(' audio') ||
      lowerName.endsWith('_sound') ||
      lowerName.endsWith(' sound')
    )
    const isImage = (
      fieldType === 'image' ||
      fieldType === 'diagram' ||
      lowerName === 'image' ||
      lowerName === 'picture' ||
      lowerName === 'photo' ||
      lowerName === 'diagram' ||
      lowerName === 'illustration' ||
      lowerName.endsWith('_image') ||
      lowerName.endsWith(' image') ||
      lowerName.endsWith('_photo') ||
      lowerName.endsWith(' photo')
    )
    if (isAudio || isImage) {
      const val = renderContext[fieldName]
      if (typeof val === 'string' && val.trim() !== '') {
        const trimmed = val.trim()
        if (
          !trimmed.startsWith('<') &&
          (
            trimmed.startsWith('http://') ||
            trimmed.startsWith('https://') ||
            trimmed.startsWith('/media/') ||
            trimmed.startsWith('[sound:') ||
            /\.(mp3|wav|ogg|m4a|aac|opus|png|jpe?g|webp|gif|svg)(\?.*)?$/i.test(trimmed)
          )
        ) {
          const kind = isAudio ? 'audio' : (fieldType === 'diagram' ? 'diagram' : 'image')
          const { html, urls } = renderMediaHtml(kind, fieldName, trimmed, content.media)
          renderContext[fieldName] = html
          if (!renderContext[`${fieldName}_url`] && urls[0]) {
            renderContext[`${fieldName}_url`] = urls[0]
          }
          if (!renderContext[`${fieldName}_urls`] && urls.length > 0) {
            renderContext[`${fieldName}_urls`] = urls
          }
        }
      }
    }
  }

  const rendered = Mustache.render(source, renderContext)
  const trustedMedia = collectTrustedMediaUrls(template, { ...content, render_context: renderContext }, source)

  const fieldValueProxyUrls: string[] = []
  if (content.field_values) {
    for (const val of Object.values(content.field_values)) {
      if (typeof val === 'string') {
        const matches = val.match(/\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/g)
        if (matches) fieldValueProxyUrls.push(...matches)
      }
    }
  }

  const managedMediaUrls = [
    ...content.media.map((item) => item.proxy_url),
    ...fieldValueProxyUrls,
  ].filter((url) => PROXY_MEDIA_RE.test(url))
  const allowedMediaUrls = [...new Set([...managedMediaUrls, ...trustedMedia.media])]
  const markup = restoreLineBreaks(
    sanitizeRenderedMarkup(rendered, new Set(allowedMediaUrls)),
  )
  const css = safeCss(template.shared_css)
  const scripts = inlineScripts.join('')
  const html = `${css ? `<style>${css}</style>` : ''}${markup}${scripts}`

  const audioFromMedia = content.media
    .filter((item) => item.mime_type.startsWith('audio/'))
    .map((item) => item.proxy_url)
  const audioFromFieldValues = Object.entries(content.field_values || {})
    .filter(([key]) => {
      const lk = key.toLowerCase()
      return lk.includes('audio') || lk.includes('sound') || lk.includes('voice')
    })
    .flatMap(([, val]) => (typeof val === 'string' ? val.match(/\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/g) || [] : []))
  const allowedAudioUrls = [
    ...new Set([...audioFromMedia, ...audioFromFieldValues, ...trustedMedia.audio]),
  ]
  const templateKey = `${template.version}:${side}`
  return {
    html,
    allowed_media_urls: allowedMediaUrls,
    allowed_audio_urls: allowedAudioUrls,
    allowed_audio_asset_ids: content.media.filter((item) => item.mime_type.startsWith('audio/')).map((item) => item.id),
    template_key: templateKey,
    shell_key: templateKey,
    has_inline_script: inlineScripts.length > 0,
    supports_live_patch: inlineScripts.length === 0,
  }
}

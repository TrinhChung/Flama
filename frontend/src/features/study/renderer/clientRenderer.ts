import DOMPurify from 'dompurify'
import Mustache from 'mustache'
import type {
  RendererSidePayload,
  StudyContentArtifact,
  StudyTemplateArtifact,
} from '../types'

const LINEBREAK_TOKEN = '__FC_LINEBREAK_TOKEN__'
const PROXY_MEDIA_RE = /^\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/
const LIBRARY_MEDIA_RE = /^\/media\/library\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}(?:\.(?:svg|png|jpe?g|webp|gif|mp3|wav|ogg|webm))?$/i
const STATIC_STROKE_RE = /^\/static\/strokes\/[a-zA-Z0-9_-]+\/[a-fA-F0-9]+\.svg$/
const SAFE_BUTTON_ONCLICK_RE =
  /^\s*document\.getElementById\(\s*['"][A-Za-z0-9_-]+['"]\s*\)\.play\(\)\s*;?\s*$/

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
    // Managed proxy URLs must come from content.media; never authorize a
    // template-injected opaque asset id merely because it appears in HTML.
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
  template: StudyTemplateArtifact,
  content: StudyContentArtifact,
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
    if (!['image', 'audio', 'diagram'].includes(fieldType)) return
    const isAudio = fieldType === 'audio'
    const fieldName = String(field.name || '')
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
]

const ALLOWED_ATTR = [
  'class', 'id', 'style', 'alt', 'title', 'role', 'dir', 'controls', 'loop',
  'muted', 'playsinline', 'autoplay', 'preload', 'poster', 'width', 'height',
  'colspan', 'rowspan', 'src', 'href', 'auto-split', 'onclick', 'loading',
  'viewBox', 'viewbox', 'xmlns', 'd', 'fill', 'stroke', 'stroke-width',
  'stroke-linecap', 'stroke-linejoin', 'stroke-dasharray', 'stroke-dashoffset',
  'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
  'transform', 'points', 'opacity', 'font-size', 'font-family', 'text-anchor',
]

function sanitizeRenderedMarkup(rawHtml: string, allowedMediaUrls: Set<string>): string {
  DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
    const attrName = data.attrName.toLowerCase()
    const attrValue = String(data.attrValue || '').trim()
    if (attrName.startsWith('on')) {
      data.keepAttr = (
        attrName === 'onclick'
        && node.nodeName.toLowerCase() === 'button'
        && SAFE_BUTTON_ONCLICK_RE.test(attrValue)
      )
      return
    }
    if (attrName === 'src' || attrName === 'href' || attrName === 'poster') {
      const tag = node.nodeName.toLowerCase()
      const isMediaTag = tag === 'img' || tag === 'audio' || tag === 'video' || tag === 'source'
      data.keepAttr = (
        (PROXY_MEDIA_RE.test(attrValue) && allowedMediaUrls.has(attrValue))
        || LIBRARY_MEDIA_RE.test(attrValue)
        || STATIC_STROKE_RE.test(attrValue)
        || (attrName === 'href' && attrValue.startsWith('https://'))
        || (isMediaTag && (attrName === 'src' || attrName === 'poster')
            && allowedMediaUrls.has(attrValue) && isApprovedMediaUrl(attrValue))
      )
      return
    }
    if (
      attrName === 'style'
      && /(?:@import|url\s*\(|expression\s*\()/i.test(attrValue)
    ) {
      data.keepAttr = false
    }
  })
  try {
    return DOMPurify.sanitize(rawHtml, {
      ALLOWED_TAGS,
      ALLOWED_ATTR,
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

export function renderStudySide(
  template: StudyTemplateArtifact,
  content: StudyContentArtifact,
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
  const rendered = Mustache.render(source, content.render_context)
  const trustedMedia = collectTrustedMediaUrls(template, content, source)
  const managedMediaUrls = content.media
    .map((item) => item.proxy_url)
    .filter((url) => PROXY_MEDIA_RE.test(url))
  const allowedMediaUrls = [...new Set([...managedMediaUrls, ...trustedMedia.media])]
  const markup = restoreLineBreaks(
    sanitizeRenderedMarkup(rendered, new Set(allowedMediaUrls)),
  )
  const css = safeCss(template.shared_css)
  const scripts = inlineScripts.join('')
  const html = `${css ? `<style>${css}</style>` : ''}${markup}${scripts}`
  const audio = content.media.filter((item) => item.mime_type.startsWith('audio/'))
  const allowedAudioUrls = [
    ...new Set([...audio.map((item) => item.proxy_url), ...trustedMedia.audio]),
  ]
  const templateKey = `${template.version}:${side}`
  return {
    html,
    allowed_media_urls: allowedMediaUrls,
    allowed_audio_urls: allowedAudioUrls,
    allowed_audio_asset_ids: audio.map((item) => item.id),
    template_key: templateKey,
    shell_key: templateKey,
    has_inline_script: inlineScripts.length > 0,
    supports_live_patch: inlineScripts.length === 0,
  }
}

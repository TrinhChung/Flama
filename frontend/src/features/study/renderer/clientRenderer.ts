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
const SAFE_MEDIA_PATH_RE = /^\/media\/[a-zA-Z0-9_./-]+\.(?:svg|png|jpe?g|webp|gif|mp3|wav|ogg|webm)$/i
const SAFE_BUTTON_ONCLICK_RE =
  /^\s*document\.getElementById\(\s*['"][A-Za-z0-9_-]+['"]\s*\)\.play\(\)\s*;?\s*$/

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
      data.keepAttr = (
        (PROXY_MEDIA_RE.test(attrValue) && allowedMediaUrls.has(attrValue))
        || LIBRARY_MEDIA_RE.test(attrValue)
        || STATIC_STROKE_RE.test(attrValue)
        || SAFE_MEDIA_PATH_RE.test(attrValue)
        || (attrName === 'href' && attrValue.startsWith('https://'))
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
  const allowedMediaUrls = content.media
    .map((item) => item.proxy_url)
    .filter((url) => PROXY_MEDIA_RE.test(url))
  const markup = restoreLineBreaks(
    sanitizeRenderedMarkup(rendered, new Set(allowedMediaUrls)),
  )
  const css = safeCss(template.shared_css)
  const scripts = inlineScripts.join('')
  const html = `${css ? `<style>${css}</style>` : ''}${markup}${scripts}`
  const audio = content.media.filter((item) => item.mime_type.startsWith('audio/'))
  const templateKey = `${template.version}:${side}`
  return {
    html,
    allowed_media_urls: allowedMediaUrls,
    allowed_audio_urls: audio.map((item) => item.proxy_url),
    allowed_audio_asset_ids: audio.map((item) => item.id),
    template_key: templateKey,
    shell_key: templateKey,
    has_inline_script: inlineScripts.length > 0,
    supports_live_patch: inlineScripts.length === 0,
  }
}

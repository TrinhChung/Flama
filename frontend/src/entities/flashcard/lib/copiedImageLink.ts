const MANAGED_MEDIA_PATH = /^\/(?:media\/)?(?:store|proxy|library)\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/

function mediaLink(raw: string): string | null {
  try {
    const url = new URL(raw.trim(), window.location.origin)
    // An image copied from Flama itself is stored as its path, like any other managed media.
    if (url.origin === window.location.origin && MANAGED_MEDIA_PATH.test(url.pathname)) return url.pathname
    if (url.protocol === 'https:') return url.href
  } catch {
    return null
  }
  return null
}

/**
 * The web address of an image copied from a page. Chrome's "Copy image" puts
 * the picture and an `<img src>` HTML snippet on the clipboard; when a card
 * cannot take uploads, that address is what can still be pasted.
 * Returns null for pictures without a usable https address (screenshots).
 */
export function copiedImageLink(data: Pick<DataTransfer, 'getData'> | null | undefined): string | null {
  if (!data) return null
  const candidates: string[] = []
  const html = data.getData('text/html')
  if (html) {
    // DOMParser builds an inert document: no scripts run and no images load.
    const src = new DOMParser().parseFromString(html, 'text/html').querySelector('img[src]')?.getAttribute('src')
    if (src) candidates.push(src)
  }
  candidates.push(...data.getData('text/uri-list').split(/\r?\n/).filter((line) => line && !line.startsWith('#')))
  for (const candidate of candidates) {
    const link = mediaLink(candidate)
    if (link) return link
  }
  return null
}

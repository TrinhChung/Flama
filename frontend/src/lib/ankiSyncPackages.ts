import { BlobReader, BlobWriter, ZipWriter } from '@zip.js/zip.js'

export interface MediaPackageEntry {
  filename: string
  blob: Blob
}

export interface CardPackageBlob {
  blob: Blob
  contentEncoding: 'gzip' | 'identity'
}

export interface DetectedMediaType {
  extension: 'jpg' | 'png' | 'gif' | 'webp' | 'svg' | 'mp3' | 'ogg' | 'wav' | 'webm'
  mimeType: string
  kind: 'image' | 'audio'
}

export function chunkNdjsonItems<T>(
  items: T[],
  toRecord: (item: T) => unknown,
  maxItems: number,
  maxBytes: number,
): T[][] {
  const itemLimit = Math.max(1, Math.floor(maxItems))
  const byteLimit = Math.max(1, Math.floor(maxBytes * 0.85))
  const encoder = new TextEncoder()
  const batches: T[][] = []
  let current: T[] = []
  let currentBytes = 0

  for (const item of items) {
    const lineBytes = encoder.encode(`${JSON.stringify(toRecord(item))}\n`).byteLength
    if (
      current.length > 0
      && (current.length >= itemLimit || currentBytes + lineBytes > byteLimit)
    ) {
      batches.push(current)
      current = []
      currentBytes = 0
    }
    current.push(item)
    currentBytes += lineBytes
  }
  if (current.length > 0) batches.push(current)
  return batches
}

export function resolveAcceptedMediaFilenames(
  acceptedFilenames: unknown,
  itemCount: number,
  packageFilenames: string[],
): Set<string> {
  if (Array.isArray(acceptedFilenames)) {
    return new Set(acceptedFilenames.filter((name): name is string => typeof name === 'string'))
  }
  return itemCount === packageFilenames.length
    ? new Set(packageFilenames)
    : new Set<string>()
}

export function rewriteMediaFieldValue(
  value: string,
  referencedMedia: Iterable<string>,
  mediaRename: ReadonlyMap<string, string>,
): string {
  let updated = value
  for (const original of referencedMedia) {
    const safe = mediaRename.get(original)
    if (updated === original) {
      updated = safe || ''
      continue
    }
    if (updated === `[sound:${original}]`) {
      updated = safe ? `[sound:${safe}]` : ''
      continue
    }
    if (updated.includes(`[sound:${original}]`)) {
      updated = updated.replaceAll(`[sound:${original}]`, safe ? `[sound:${safe}]` : '')
    }
    if (safe && updated.includes(original)) {
      updated = updated
        .replaceAll(`src="${original}"`, `src="${safe}"`)
        .replaceAll(`src='${original}'`, `src='${safe}'`)
    }
  }
  return updated
}

const MEDIA_BY_EXTENSION: Record<string, DetectedMediaType> = {
  jpg: { extension: 'jpg', mimeType: 'image/jpeg', kind: 'image' },
  jpeg: { extension: 'jpg', mimeType: 'image/jpeg', kind: 'image' },
  png: { extension: 'png', mimeType: 'image/png', kind: 'image' },
  gif: { extension: 'gif', mimeType: 'image/gif', kind: 'image' },
  webp: { extension: 'webp', mimeType: 'image/webp', kind: 'image' },
  svg: { extension: 'svg', mimeType: 'image/svg+xml', kind: 'image' },
  mp3: { extension: 'mp3', mimeType: 'audio/mpeg', kind: 'audio' },
  ogg: { extension: 'ogg', mimeType: 'audio/ogg', kind: 'audio' },
  wav: { extension: 'wav', mimeType: 'audio/wav', kind: 'audio' },
  webm: { extension: 'webm', mimeType: 'audio/webm', kind: 'audio' },
}

function startsWithBytes(bytes: Uint8Array, signature: number[]): boolean {
  return signature.every((value, index) => bytes[index] === value)
}

function asciiAt(bytes: Uint8Array, offset: number, value: string): boolean {
  return [...value].every((character, index) => bytes[offset + index] === character.charCodeAt(0))
}

/**
 * Anki accepts media filenames without a conventional extension. Detect the
 * actual format first so package entry names always use a backend-supported,
 * content-derived extension. The original extension is only a compatibility
 * fallback for formats whose signature is not conclusive (notably SVG).
 */
export function detectMediaType(bytes: Uint8Array, originalFilename: string): DetectedMediaType {
  if (startsWithBytes(bytes, [0xff, 0xd8, 0xff])) return MEDIA_BY_EXTENSION.jpg
  if (startsWithBytes(bytes, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
    return MEDIA_BY_EXTENSION.png
  }
  if (asciiAt(bytes, 0, 'GIF87a') || asciiAt(bytes, 0, 'GIF89a')) return MEDIA_BY_EXTENSION.gif
  if (asciiAt(bytes, 0, 'RIFF') && asciiAt(bytes, 8, 'WEBP')) return MEDIA_BY_EXTENSION.webp
  if (asciiAt(bytes, 0, 'RIFF') && asciiAt(bytes, 8, 'WAVE')) return MEDIA_BY_EXTENSION.wav
  if (asciiAt(bytes, 0, 'OggS')) return MEDIA_BY_EXTENSION.ogg
  if (startsWithBytes(bytes, [0x1a, 0x45, 0xdf, 0xa3])) return MEDIA_BY_EXTENSION.webm
  if (asciiAt(bytes, 0, 'ID3') || (bytes[0] === 0xff && (bytes[1] & 0xe0) === 0xe0)) {
    return MEDIA_BY_EXTENSION.mp3
  }

  const textPrefix = new TextDecoder().decode(bytes.subarray(0, Math.min(bytes.length, 4096)))
    .replace(/^\uFEFF/, '')
    .trimStart()
  if (/^(?:<\?xml[^>]*>\s*)?(?:<!--[\s\S]*?-->\s*)*<svg(?:\s|>)/i.test(textPrefix)) {
    return MEDIA_BY_EXTENSION.svg
  }

  const extension = originalFilename.toLowerCase().split('.').pop()?.replace(/[^a-z0-9]/g, '') || ''
  const fallback = MEDIA_BY_EXTENSION[extension]
  if (fallback) return fallback
  throw new Error(`Không nhận diện được định dạng media "${originalFilename}".`)
}

export async function buildMediaZip(entries: MediaPackageEntry[]): Promise<Blob> {
  const writer = new ZipWriter(new BlobWriter('application/zip'))
  try {
    for (const entry of entries) {
      await writer.add(entry.filename, new BlobReader(entry.blob), {
        level: 0,
        useWebWorkers: true,
      })
    }
    return await writer.close()
  } catch (error) {
    await writer.close().catch(() => undefined)
    throw error
  }
}

export function shouldFlushMediaPackage(
  currentBytes: number,
  currentEntries: number,
  nextBytes: number,
  maxBytes: number,
  maxEntries: number
): boolean {
  if (currentEntries === 0) return false
  return currentEntries >= maxEntries || currentBytes + nextBytes > Math.floor(maxBytes * 0.85)
}

export async function uploadPackageWithRetry<T>(
  upload: () => Promise<T>,
  wait: (delayMs: number) => Promise<unknown> = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  maxAttempts = 3
): Promise<T> {
  let lastError: unknown = new Error('Không upload được package.')
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      return await upload()
    } catch (error) {
      lastError = error
      if (attempt < maxAttempts - 1) await wait(300 * 2 ** attempt)
    }
  }
  throw lastError
}

export async function buildCardNdjsonPackage(records: unknown[]): Promise<CardPackageBlob> {
  const ndjson = `${records.map((record) => JSON.stringify(record)).join('\n')}\n`
  const source = new Blob([ndjson], { type: 'application/x-ndjson' })
  if (typeof CompressionStream === 'undefined') {
    return { blob: source, contentEncoding: 'identity' }
  }
  const stream = source.stream().pipeThrough(new CompressionStream('gzip'))
  return {
    blob: await new Response(stream).blob(),
    contentEncoding: 'gzip',
  }
}

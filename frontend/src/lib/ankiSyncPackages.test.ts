import { describe, expect, it, vi } from 'vitest'
import {
  buildCardNdjsonPackage,
  buildMediaZip,
  detectMediaType,
  shouldFlushMediaPackage,
  uploadPackageWithRetry,
} from './ankiSyncPackages'

describe('ankiSyncPackages', () => {
  it('uses deterministic package boundaries by byte and entry limits', () => {
    expect(shouldFlushMediaPackage(100, 1, 50, 1_000, 10)).toBe(false)
    expect(shouldFlushMediaPackage(800, 2, 100, 1_000, 10)).toBe(true)
    expect(shouldFlushMediaPackage(100, 10, 1, 1_000, 10)).toBe(true)
  })

  it('creates a ZIP blob without embedding base64 JSON', async () => {
    const blob = await buildMediaZip([{ filename: 'abc.png', blob: new Blob(['png-data']) }])
    const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer())
    expect([...signature]).toEqual([0x50, 0x4b, 0x03, 0x04])
  })

  it('canonicalizes an extensionless Anki WebP from its byte signature', () => {
    const bytes = new Uint8Array([
      0x52, 0x49, 0x46, 0x46, 0x88, 0x14, 0x00, 0x00,
      0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x20,
    ])

    expect(detectMediaType(bytes, 'OIP.0sMoiUX6ozQ6vh4FfRQS_gHaE6')).toEqual({
      extension: 'webp',
      mimeType: 'image/webp',
      kind: 'image',
    })
  })

  it('prefers the byte signature over a misleading filename extension', () => {
    const bytes = new Uint8Array([
      0x52, 0x49, 0x46, 0x46, 0x88, 0x14, 0x00, 0x00,
      0x57, 0x45, 0x42, 0x50, 0x56, 0x50, 0x38, 0x20,
    ])

    expect(detectMediaType(bytes, 'wrong.mp3').extension).toBe('webp')
  })

  it('creates a card NDJSON package that can be transported as one blob', async () => {
    const result = await buildCardNdjsonPackage([{ ankiNoteId: 1 }, { ankiNoteId: 2 }])
    expect(result.blob.size).toBeGreaterThan(0)
    expect(['gzip', 'identity']).toContain(result.contentEncoding)
  })

  it('keeps a failed package fatal after bounded retries', async () => {
    const upload = vi.fn().mockRejectedValue(new Error('package rejected'))
    const wait = vi.fn().mockResolvedValue(undefined)

    await expect(uploadPackageWithRetry(upload, wait)).rejects.toThrow('package rejected')
    expect(upload).toHaveBeenCalledTimes(3)
    expect(wait).toHaveBeenCalledTimes(2)
  })
})

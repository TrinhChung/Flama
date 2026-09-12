// @vitest-environment jsdom

import { describe, expect, it, vi, beforeEach } from 'vitest'
import { compressImage, MAX_IMAGE_UPLOAD_BYTES } from './imageCompression'

describe('imageCompression', () => {
  beforeEach(() => {
    // Mock HTMLCanvasElement.prototype.getContext and toBlob in jsdom
    HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
      drawImage: vi.fn(),
    }) as any

    HTMLCanvasElement.prototype.toBlob = vi.fn((callback, type) => {
      const mockBlob = new Blob(['mock-compressed-bytes'], { type: type || 'image/webp' })
      callback(mockBlob)
    }) as any
  })

  it('defines MAX_IMAGE_UPLOAD_BYTES as 2MB', () => {
    expect(MAX_IMAGE_UPLOAD_BYTES).toBe(2 * 1024 * 1024)
  })

  it('compresses a dummy image blob to webp with maxDimension scaling', async () => {
    // Mock createImageBitmap
    const mockBitmap = {
      width: 3840,
      height: 2160,
      close: vi.fn(),
    }
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(mockBitmap))

    const dummyBlob = new Blob(['sample-data-large'], { type: 'image/png' })
    const result = await compressImage(dummyBlob, {
      maxDimension: 1600,
      quality: 0.85,
    })

    expect(result.blob).toBeDefined()
    expect(result.file).toBeDefined()
    expect(result.width).toBe(1600)
    expect(result.height).toBe(900) // 3840x2160 scaled to max 1600 -> 1600x900
    expect(mockBitmap.close).toHaveBeenCalled()
  })

  it('does not upscale images that are smaller than maxDimension', async () => {
    const mockBitmap = {
      width: 800,
      height: 600,
      close: vi.fn(),
    }
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(mockBitmap))

    const dummyBlob = new Blob(['sample-data-small'], { type: 'image/jpeg' })
    const result = await compressImage(dummyBlob, {
      maxDimension: 1600,
    })

    expect(result.width).toBe(800)
    expect(result.height).toBe(600)
  })
})

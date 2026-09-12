/**
 * Utility for client-side image compression and resizing using HTML Canvas.
 * Ensures clipboard images and uploaded photos are optimized before sending over network.
 */

export const MAX_IMAGE_UPLOAD_BYTES = 2 * 1024 * 1024 // 2 MB

export interface CompressImageOptions {
  /** Maximum width or height in pixels. Default is 1600px. */
  maxDimension?: number
  /** Compression quality between 0.0 and 1.0. Default is 0.85. */
  quality?: number
  /** Fallback MIME type if WebP is not supported. Default is image/jpeg. */
  fallbackMimeType?: 'image/jpeg' | 'image/png'
  /** Desired output filename. Default is 'compressed.webp'. */
  filename?: string
}

export interface CompressImageResult {
  file: File
  blob: Blob
  width: number
  height: number
  originalSizeBytes: number
  compressedSizeBytes: number
}

interface LoadedDrawable {
  width: number
  height: number
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void
  cleanup: () => void
}

async function loadDrawable(source: Blob | File): Promise<LoadedDrawable> {
  // Use createImageBitmap if available (faster, off-main-thread)
  if (typeof createImageBitmap === 'function') {
    try {
      const bitmap = await createImageBitmap(source)
      return {
        width: bitmap.width,
        height: bitmap.height,
        draw: (ctx, w, h) => ctx.drawImage(bitmap, 0, 0, w, h),
        cleanup: () => bitmap.close(),
      }
    } catch {
      // Fallback to HTMLImageElement on bitmap decode errors
    }
  }

  // Fallback using HTMLImageElement
  return new Promise((resolve, reject) => {
    const img = new Image()
    const url = URL.createObjectURL(source)
    let done = false

    const cleanup = () => {
      if (done) return
      done = true
      clearTimeout(timer)
      URL.revokeObjectURL(url)
    }

    const timer = setTimeout(() => {
      cleanup()
      reject(new Error('Không thể tải hoặc giải mã tệp hình ảnh (quá thời gian).'))
    }, 1500)

    img.onload = () => {
      const width = img.naturalWidth || img.width
      const height = img.naturalHeight || img.height
      cleanup()
      resolve({
        width,
        height,
        draw: (ctx, w, h) => ctx.drawImage(img, 0, 0, w, h),
        cleanup: () => {},
      })
    }
    img.onerror = () => {
      cleanup()
      reject(new Error('Không thể tải hoặc giải mã tệp hình ảnh.'))
    }
    img.src = url
  })
}

/**
 * Compresses and scales an image down to fit within maxDimension.
 * Converts to WebP format (or JPEG fallback) with high visual fidelity.
 */
export async function compressImage(
  source: Blob | File,
  options: CompressImageOptions = {},
): Promise<CompressImageResult> {
  const maxDimension = options.maxDimension ?? 1600
  const quality = options.quality ?? 0.85
  const fallbackMimeType = options.fallbackMimeType ?? 'image/jpeg'
  const originalSizeBytes = source.size

  const loaded = await loadDrawable(source)

  try {
    let { width, height } = loaded
    if (width <= 0 || height <= 0) {
      throw new Error('Kích thước hình ảnh không hợp lệ.')
    }

    // Scale maintaining aspect ratio without upscaling
    if (width > maxDimension || height > maxDimension) {
      const scale = Math.min(maxDimension / width, maxDimension / height)
      width = Math.max(1, Math.round(width * scale))
      height = Math.max(1, Math.round(height * scale))
    }

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      throw new Error('Trình duyệt không hỗ trợ Canvas 2D context.')
    }

    loaded.draw(ctx, width, height)

    // Attempt WebP first, fallback to JPEG
    let blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/webp', quality)
    })

    let ext = 'webp'
    if (!blob || blob.type !== 'image/webp') {
      blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob(resolve, fallbackMimeType, quality)
      })
      ext = fallbackMimeType === 'image/jpeg' ? 'jpg' : 'png'
    }

    if (!blob) {
      throw new Error('Không thể nén và xuất hình ảnh từ Canvas.')
    }

    const rawName = (source as File).name || options.filename || `pasted_image.${ext}`
    const baseName = rawName.substring(0, rawName.lastIndexOf('.')) || rawName
    const finalFilename = `${baseName}.${ext}`

    const file = new File([blob], finalFilename, {
      type: blob.type,
      lastModified: Date.now(),
    })

    return {
      file,
      blob,
      width,
      height,
      originalSizeBytes,
      compressedSizeBytes: blob.size,
    }
  } finally {
    loaded.cleanup()
  }
}

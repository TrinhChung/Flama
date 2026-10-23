import { useMemo } from 'react'
import QRCode from 'qrcode'

/** QR modules for `url` as one SVG path (1-module quiet zone), or null when unavailable. */
export function useQrCodePath(url: string) {
  return useMemo(() => {
    if (!url) return null
    try {
      const qr = QRCode.create(url, { errorCorrectionLevel: 'M' })
      const modSize = qr.modules.size
      const margin = 1
      const totalSize = modSize + margin * 2
      let path = ''
      for (let r = 0; r < modSize; r++) {
        for (let c = 0; c < modSize; c++) {
          if (qr.modules.get(r, c)) {
            path += `M${c + margin},${r + margin}h1v1h-1z `
          }
        }
      }
      return { path, totalSize }
    } catch {
      return null
    }
  }, [url])
}

/**
 * High-Fidelity Client-Side PDF Generation Engine for Worksheets.
 *
 * Uses `modern-screenshot` and `jspdf` to capture rendered A4 worksheet pages
 * at high print resolution (200-300 DPI) and compile them into a tamper-proof,
 * flattened binary PDF document.
 *
 * Security & Anti-Crawl:
 * - Rasterized / flattened canvas into PDF: Watermarks, footer brand ('Flama'),
 *   domain names, and QR codes are permanently baked into the image matrix.
 * - Absolutely NO raw HTML is returned or saved to the client's disk.
 */

import { jsPDF } from 'jspdf'
import { domToJpeg } from 'modern-screenshot'
import { createElement } from 'react'
import { createRoot } from 'react-dom/client'
import { flushSync } from 'react-dom'
import { WorksheetPageRenderer } from '../components/WorksheetPageRenderer'
import type { WorksheetPreviewResponse } from '../types'

export interface PdfExportProgress {
  currentPage: number
  totalPages: number
  status: string
}

export interface GeneratePdfOptions {
  scale?: number
  quality?: number
  onProgress?: (progress: PdfExportProgress) => void
}

/**
 * Render all pages of a worksheet preview into a multi-page PDF document.
 */
export async function generateWorksheetPdf(
  previewData: WorksheetPreviewResponse,
  options: GeneratePdfOptions = {},
): Promise<{ blob: Blob; filename: string }> {
  const { template, options: layoutOptions, pages } = previewData
  if (!pages || pages.length === 0) {
    throw new Error('Không có trang nào để xuất PDF.')
  }

  const isLandscape = layoutOptions.orientation === 'landscape'
  const orientation = isLandscape ? 'l' : 'p'
  const pageWmm = isLandscape ? 297 : 210
  const pageHmm = isLandscape ? 210 : 297
  const scale = options.scale ?? 2 // 2x gives crisp ~200-300 DPI on A4
  const quality = options.quality ?? 0.94

  const totalPages = pages.length
  let pdf: jsPDF | null = null

  for (let i = 0; i < totalPages; i++) {
    const page = pages[i]

    options.onProgress?.({
      currentPage: i + 1,
      totalPages,
      status: `Đang kết xuất trang ${i + 1}/${totalPages}...`,
    })

    // 1. Create an off-screen container with exact A4 physical dimensions
    const container = document.createElement('div')
    container.style.cssText =
      'position:fixed;left:-9999px;top:0;z-index:-9999;pointer-events:none;' +
      `width:${pageWmm}mm;height:${pageHmm}mm;background:#ffffff;overflow:hidden;`
    document.body.appendChild(container)

    // 2. Render WorksheetPageRenderer synchronously into the container
    const root = createRoot(container)
    flushSync(() => {
      root.render(
        createElement(WorksheetPageRenderer, {
          page,
          template,
          options: layoutOptions,
          zoom: 1,
          isPrintMode: true,
        }),
      )
    })

    // 3. Wait for layout, fonts, and SVG paths to settle
    await new Promise((resolve) => setTimeout(resolve, 80))

    const pageEl = (container.firstElementChild as HTMLElement) || container

    // 4. Capture page to high-res JPEG
    let jpegDataUrl = ''
    try {
      jpegDataUrl = await domToJpeg(pageEl, {
        scale,
        quality,
        backgroundColor: '#ffffff',
        features: {
          removeControlCharacter: true,
        },
      })
    } catch (captureErr) {
      // Cleanup on failure
      root.unmount()
      if (container.parentNode) container.parentNode.removeChild(container)
      throw new Error(
        `Lỗi khi kết xuất đồ họa trang ${i + 1}: ${captureErr instanceof Error ? captureErr.message : String(captureErr)}`,
      )
    }

    // 5. Cleanup DOM node
    root.unmount()
    if (container.parentNode) {
      container.parentNode.removeChild(container)
    }

    // 6. Initialize or append to jsPDF
    if (!pdf) {
      pdf = new jsPDF({
        orientation,
        unit: 'mm',
        format: 'a4',
        compress: true,
      })
    } else {
      pdf.addPage('a4', orientation)
    }

    // Embed flattened image covering 100% of the A4 page
    pdf.addImage(jpegDataUrl, 'JPEG', 0, 0, pageWmm, pageHmm, undefined, 'FAST')
  }

  if (!pdf) {
    throw new Error('Không thể khởi tạo tài liệu PDF.')
  }

  const filename = `flama_worksheet_${template.id || 'export'}_${layoutOptions.paper_size || 'a4'}.pdf`
  const blob = pdf.output('blob')

  return { blob, filename }
}

/**
 * Trigger immediate browser download of a generated PDF Blob.
 */
export function downloadPdfBlob(blob: Blob, filename = 'flama_worksheet.pdf'): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => {
    URL.revokeObjectURL(url)
  }, 60000)
}

/**
 * Open a generated PDF Blob in a new browser tab using the browser's built-in PDF viewer.
 */
export function openPdfBlobInNewTab(blob: Blob): Window | null {
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')
  setTimeout(() => {
    URL.revokeObjectURL(url)
  }, 120000)
  return win
}

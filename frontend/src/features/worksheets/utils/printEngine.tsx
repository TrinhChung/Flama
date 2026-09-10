import { createElement } from 'react'
import { flushSync } from 'react-dom'
import { createRoot, type Root } from 'react-dom/client'
import { WorksheetPageRenderer } from '../components/WorksheetPageRenderer'
import type { WorksheetPreviewResponse } from '../types'

const PRINT_ROOT_ID = 'flama-worksheet-print-root'
let activeCleanup: (() => void) | null = null

function waitForNextPaint(): Promise<void> {
  return new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  })
}

async function waitForPrintableAssets(host: HTMLElement): Promise<void> {
  const fontsReady = document.fonts?.ready?.catch(() => undefined) ?? Promise.resolve()
  const imagesReady = Promise.all(
    Array.from(host.querySelectorAll('img')).map(async (image) => {
      if (!image.complete) {
        await new Promise<void>((resolve) => {
          image.addEventListener('load', () => resolve(), { once: true })
          image.addEventListener('error', () => resolve(), { once: true })
        })
      }
      if (typeof image.decode === 'function') {
        await image.decode().catch(() => undefined)
      }
    }),
  )

  await Promise.race([
    Promise.all([fontsReady, imagesReady]),
    new Promise<void>((resolve) => window.setTimeout(resolve, 2500)),
  ])
  await waitForNextPaint()
}

function createPrintStyles(orientation: 'portrait' | 'landscape'): HTMLStyleElement {
  const style = document.createElement('style')
  style.textContent = `
    @media screen {
      #${PRINT_ROOT_ID} {
        position: fixed !important;
        left: -100000px !important;
        top: 0 !important;
        width: 1px !important;
        height: 1px !important;
        overflow: hidden !important;
      }
    }
    @media print {
      @page { size: A4 ${orientation}; margin: 0; }
      html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
      body > * { display: none !important; }
      body > #${PRINT_ROOT_ID} { display: block !important; }
      #${PRINT_ROOT_ID}, #${PRINT_ROOT_ID} .flama-print-document {
        position: static !important;
        width: auto !important;
        height: auto !important;
        overflow: visible !important;
      }
      #${PRINT_ROOT_ID} .flama-print-page {
        display: block !important;
        break-after: page;
        page-break-after: always;
      }
      #${PRINT_ROOT_ID} .flama-print-page:last-child {
        break-after: auto;
        page-break-after: auto;
      }
    }
  `
  return style
}

/**
 * Render the existing React pages once into a temporary print tree. The native
 * browser dialog also provides "Save as PDF" without a PDF/canvas dependency.
 */
export async function printWorksheet(preview: WorksheetPreviewResponse): Promise<void> {
  if (!preview.pages.length) {
    throw new Error('Không có trang nào để in.')
  }

  activeCleanup?.()

  const host = document.createElement('div')
  host.id = PRINT_ROOT_ID
  host.setAttribute('aria-hidden', 'true')
  const style = createPrintStyles(preview.options.orientation || 'portrait')
  document.head.appendChild(style)
  document.body.appendChild(host)

  let root: Root | null = createRoot(host)
  let cleanupTimer: number | null = null
  let cleaned = false
  const cleanup = () => {
    if (cleaned) return
    cleaned = true
    if (cleanupTimer !== null) window.clearTimeout(cleanupTimer)
    window.removeEventListener('afterprint', cleanup)
    root?.unmount()
    root = null
    host.remove()
    style.remove()
    if (activeCleanup === cleanup) activeCleanup = null
  }
  activeCleanup = cleanup

  try {
    flushSync(() => {
      root?.render(
        createElement(
          'div',
          { className: 'flama-print-document' },
          preview.pages.map((page) =>
            createElement(
              'div',
              { className: 'flama-print-page', key: page.page_number },
              createElement(WorksheetPageRenderer, {
                page,
                template: preview.template,
                options: preview.options,
                fieldMapping: preview.field_mapping,
                zoom: 1,
                isPrintMode: true,
              }),
            ),
          ),
        ),
      )
    })

    await waitForPrintableAssets(host)
    window.addEventListener('afterprint', cleanup, { once: true })
    cleanupTimer = window.setTimeout(cleanup, 60_000)
    window.print()
  } catch (error) {
    cleanup()
    throw error
  }
}

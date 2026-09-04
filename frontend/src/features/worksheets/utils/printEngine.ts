/**
 * Isolated Print Engine for High-Fidelity A4 Worksheet Printing & Downloads.
 */

export function isMobileDevice(): boolean {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const isTouch =
    navigator.maxTouchPoints > 0 ||
    (window.matchMedia && window.matchMedia('(pointer: coarse)').matches)
  const isMobileUa = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)
  return isMobileUa || (Boolean(isTouch) && window.innerWidth < 1024)
}

export function openWorksheetInNewTab(htmlContent: string): Window | null {
  const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const win = window.open(url, '_blank')
  if (!win) {
    // If popup was blocked, fallback to download
    downloadWorksheetHtml(htmlContent)
    return null
  }
  setTimeout(() => {
    URL.revokeObjectURL(url)
  }, 60000)
  return win
}

export function printWorksheetHtml(htmlContent: string): void {
  // Mobile devices (iOS Safari & Android Chrome):
  // Invisible iframes are blocked or fail to invoke native AirPrint/Print dialog.
  // Opening the document via a Blob URL in a dedicated window or triggering print in a new tab
  // provides reliable native printing across iOS and Android.
  if (isMobileDevice()) {
    const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const printWindow = window.open(url, '_blank')
    if (printWindow) {
      printWindow.focus()
      setTimeout(() => {
        try {
          printWindow.print()
        } catch {
          // Fallback handled by in-page print button
        }
      }, 700)
      setTimeout(() => {
        URL.revokeObjectURL(url)
      }, 60000)
      return
    }
    // If popup blocked on mobile, fallback to download
    downloadWorksheetHtml(htmlContent)
    return
  }

  // Desktop workflow: Use a hidden iframe for seamless native printing without popup blockers
  let iframe = document.getElementById('flama-worksheet-print-frame') as HTMLIFrameElement | null

  if (iframe && iframe.parentNode) {
    iframe.parentNode.removeChild(iframe)
  }

  iframe = document.createElement('iframe')
  iframe.id = 'flama-worksheet-print-frame'
  iframe.style.position = 'fixed'
  iframe.style.right = '0'
  iframe.style.bottom = '0'
  iframe.style.width = '0'
  iframe.style.height = '0'
  iframe.style.border = '0'
  iframe.style.visibility = 'hidden'
  document.body.appendChild(iframe)

  const doc = iframe.contentWindow?.document
  if (!doc) {
    // Fallback to new window if iframe document is unavailable
    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.open()
      printWindow.document.write(htmlContent)
      printWindow.document.close()
      printWindow.focus()
      setTimeout(() => {
        printWindow.print()
      }, 500)
    }
    return
  }

  doc.open()
  doc.write(htmlContent)
  doc.close()

  // Wait for SVGs and fonts to settle before printing
  setTimeout(() => {
    try {
      iframe?.contentWindow?.focus()
      iframe?.contentWindow?.print()
    } catch {
      // Fallback
      window.print()
    }
  }, 400)
}

export function downloadWorksheetHtml(htmlContent: string, filename = 'flama_worksheet.html'): void {
  const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

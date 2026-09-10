// @vitest-environment jsdom

import { describe, expect, it, vi } from 'vitest'
import { downloadPdfBlob, openPdfBlobInNewTab } from './pdfEngine'

describe('pdfEngine utilities', () => {
  it('downloads PDF blob with correct filename and cleans up object URL', () => {
    const fakeBlob = new Blob(['fake-pdf-binary'], { type: 'application/pdf' })
    const createUrlSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-pdf-url')
    const revokeUrlSpy = vi.spyOn(URL, 'revokeObjectURL')

    const appendChildSpy = vi.spyOn(document.body, 'appendChild')
    const removeChildSpy = vi.spyOn(document.body, 'removeChild')

    downloadPdfBlob(fakeBlob, 'test_worksheet.pdf')

    expect(createUrlSpy).toHaveBeenCalledWith(fakeBlob)
    expect(appendChildSpy).toHaveBeenCalled()
    expect(removeChildSpy).toHaveBeenCalled()

    createUrlSpy.mockRestore()
    revokeUrlSpy.mockRestore()
    appendChildSpy.mockRestore()
    removeChildSpy.mockRestore()
  })

  it('opens PDF blob in a new tab', () => {
    const fakeBlob = new Blob(['fake-pdf-binary'], { type: 'application/pdf' })
    const createUrlSpy = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:mock-pdf-url')
    const openSpy = vi.spyOn(window, 'open').mockReturnValue({} as Window)

    const win = openPdfBlobInNewTab(fakeBlob)

    expect(createUrlSpy).toHaveBeenCalledWith(fakeBlob)
    expect(openSpy).toHaveBeenCalledWith('blob:mock-pdf-url', '_blank')
    expect(win).toBeDefined()

    createUrlSpy.mockRestore()
    openSpy.mockRestore()
  })
})

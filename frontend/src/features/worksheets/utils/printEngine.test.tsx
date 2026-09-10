// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorksheetPreviewResponse } from '../types'

vi.mock('../components/WorksheetPageRenderer', () => ({
  WorksheetPageRenderer: ({ page }: { page: { page_number: number } }) => (
    <div data-testid="print-page">Page {page.page_number}</div>
  ),
}))

import { printWorksheet } from './printEngine'

const preview: WorksheetPreviewResponse = {
  template: {
    id: 'deck_table',
    name_vi: 'Bảng',
    name_en: 'Table',
    description_vi: '',
    description_en: '',
    category: 'table',
    supported_orientations: ['portrait'],
    default_orientation: 'portrait',
    default_rows_per_page: 10,
    field_slots: [],
    default_options: {},
  },
  deck_id: 1,
  deck_name: 'Deck',
  options: { orientation: 'portrait' },
  field_mapping: {},
  total_items: 2,
  total_pages: 2,
  warnings: [],
  pages: [1, 2].map((pageNumber) => ({
    page_number: pageNumber,
    total_pages: 2,
    header: {
      title: 'Deck',
      subtitle: '',
      deck_name: 'Deck',
      show_student_info: false,
      show_date: false,
    },
    items: [],
  })),
}

describe('printWorksheet', () => {
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
      callback(0)
      return 1
    })
  })

  it('prints all pages without opening a tab and cleans up after printing', async () => {
    const openSpy = vi.spyOn(window, 'open')
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {
      window.dispatchEvent(new Event('afterprint'))
    })

    await printWorksheet(preview)

    expect(printSpy).toHaveBeenCalledOnce()
    expect(openSpy).not.toHaveBeenCalled()
    expect(document.getElementById('flama-worksheet-print-root')).toBeNull()
  })

  it('rejects an empty worksheet', async () => {
    await expect(
      printWorksheet({ ...preview, pages: [], total_pages: 0 }),
    ).rejects.toThrow('Không có trang nào để in.')
  })
})

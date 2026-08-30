// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DeckWorksheetModal } from './components/DeckWorksheetModal'
import * as worksheetApi from './api'

describe('DeckWorksheetModal', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  const mockMeta = {
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    total_notes: 30,
    note_types: [
      {
        id: 'nt1',
        name: 'Vocabulary Note',
        fields: ['Expression', 'Reading', 'Meaning'],
        note_count: 30,
      },
    ],
    suggested_mappings: {
      kanji: 'Expression',
      reading: 'Reading',
      meaning: 'Meaning',
      word: 'Expression',
      prompt_reading: 'Reading',
      prompt_meaning: 'Meaning',
    },
    templates: [
      {
        id: 'kanji_stroke',
        name_vi: 'Luyện viết Kanji chuẩn',
        name_en: 'Kanji Stroke Practice',
        description_vi: 'Mẫu chữ Hán chuẩn với sơ đồ nét.',
        description_en: 'Standard Kanji practice.',
        category: 'kanji' as const,
        supported_orientations: ['portrait' as const, 'landscape' as const],
        default_orientation: 'portrait' as const,
        default_rows_per_page: 5,
        field_slots: [
          {
            key: 'kanji',
            label_vi: 'Trường Kanji',
            label_en: 'Kanji',
            required: true,
          },
        ],
        default_options: {
          grid_style: 'cross' as const,
          trace_count: 2,
          practice_count: 5,
        },
      },
      {
        id: 'vocab_writing',
        name_vi: 'Luyện viết từ vựng',
        name_en: 'Vocab Writing',
        description_vi: 'Bảng luyện viết từ vựng.',
        description_en: 'Vocab table.',
        category: 'vocabulary' as const,
        supported_orientations: ['portrait' as const, 'landscape' as const],
        default_orientation: 'portrait' as const,
        default_rows_per_page: 10,
        field_slots: [
          {
            key: 'word',
            label_vi: 'Trường từ vựng',
            label_en: 'Word',
            required: true,
          },
        ],
        default_options: {
          rows_per_page: 10,
        },
      },
    ],
  }

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(mockMeta)
  })

  afterEach(() => {
    if (root && container) {
      act(() => {
        root?.unmount()
      })
      container.remove()
    }
    container = null
    root = null
    vi.restoreAllMocks()
  })

  it('renders modal and displays loaded templates', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
        />,
      )
    })

    // Wait for async meta fetch
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    expect(document.body.textContent).toContain('Xuất bài tập in ấn / PDF (A4)')
    expect(document.body.textContent).toContain('Luyện viết Kanji chuẩn')
    expect(document.body.textContent).toContain('Luyện viết từ vựng')
  })

  it('navigates through steps to field mapping and layout', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // Step 1: Click Continue to Fields
    const nextBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Dữ liệu'),
    )
    expect(nextBtn).toBeDefined()

    await act(async () => {
      nextBtn?.click()
    })

    // Verify Step 2: Dữ liệu
    expect(document.body.textContent).toContain('Bước 2: Ánh xạ trường dữ liệu')
    expect(document.body.textContent).toContain('Trường Kanji')

    // Click Continue to Layout
    const toLayoutBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Bố cục'),
    )
    expect(toLayoutBtn).toBeDefined()

    await act(async () => {
      toLayoutBtn?.click()
    })

    // Verify Step 3: Bố cục
    expect(document.body.textContent).toContain('Bước 3: Tùy chỉnh Bố cục')
    expect(document.body.textContent).toContain('Kiểu đường kẻ')

    // Test direct stepper navigation back to step 1
    const step1Btn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('1. Mẫu'),
    )
    expect(step1Btn).toBeDefined()
    await act(async () => {
      step1Btn?.click()
    })
    expect(document.body.textContent).toContain('Bước 1: Chọn mẫu bài tập phù hợp')
  })

  it('generates preview and displays workbench with page navigation', async () => {
    const mockPreviewData = {
      template: mockMeta.templates[0],
      deck_id: 1,
      deck_name: 'JLPT N5 Core',
      options: { orientation: 'portrait' as const, rows_per_page: 5 },
      field_mapping: { kanji: 'Expression' },
      total_items: 2,
      total_pages: 1,
      pages: [
        {
          page_number: 1,
          total_pages: 1,
          header: {
            title: 'JLPT N5 Core - Bài tập',
            subtitle: 'Luyện viết mỗi ngày',
            deck_name: 'JLPT N5 Core',
            show_student_info: true,
            show_date: true,
          },
          items: [
            {
              type: 'kanji' as const,
              note_id: '1',
              char: '日',
              hex: '65e5',
              has_stroke: true,
              stroke_svg: null,
              stroke_url: null,
              reading: 'にち',
              meaning: 'Mặt trời, ngày',
              source_word: '日',
            },
          ],
        },
      ],
      warnings: [],
    }

    vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockResolvedValue(mockPreviewData as any)

    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // Navigate to step 2
    const nextBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Dữ liệu'),
    )
    await act(async () => {
      nextBtn?.click()
    })

    // Navigate to step 3
    const toLayoutBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Bố cục'),
    )
    await act(async () => {
      toLayoutBtn?.click()
    })

    // Generate preview
    const genPreviewBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Xem trước bài tập'),
    )
    expect(genPreviewBtn).toBeDefined()

    await act(async () => {
      genPreviewBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50))
    })

    // Verify preview workbench elements
    expect(document.body.textContent).toContain('Trang trước')
    expect(document.body.textContent).toContain('Trang sau')
    expect(document.body.textContent).toContain('In ngay (Print / PDF)')
    expect(document.body.textContent).toContain('Tải file in (HTML)')
    expect(document.body.textContent).toContain('日')
  })
})

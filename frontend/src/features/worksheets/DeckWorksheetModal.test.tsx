// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DeckWorksheetModal } from './components/DeckWorksheetModal'
import * as worksheetApi from './api'

describe('DeckWorksheetModal Live Studio', () => {
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
      {
        id: 'deck_table',
        name_vi: 'Bảng dữ liệu bộ thẻ tuỳ biến',
        name_en: 'Generic Deck Table',
        description_vi: 'Mẫu bảng đa năng cho phép chọn tự do các trường.',
        description_en: 'Generic Table.',
        category: 'table' as const,
        supported_orientations: ['portrait' as const, 'landscape' as const],
        default_orientation: 'portrait' as const,
        default_rows_per_page: 15,
        field_slots: [
          {
            key: 'custom_columns',
            label_vi: 'Cột hiển thị',
            label_en: 'Custom Columns',
            required: true,
          },
        ],
        default_options: {
          rows_per_page: 15,
        },
      },
      {
        id: 'genkouyoushi',
        name_vi: 'Giấy làm văn Genkō Yōshi / 作文纸 (400 ô)',
        name_en: 'Genkō Yōshi Essay Sheet (400 Grids)',
        description_vi: 'Mẫu giấy kẻ ô vuông chuẩn 400 ô hoặc 200 ô để luyện viết văn.',
        description_en: 'Standard 400-grid or 200-grid essay paper.',
        category: 'essay' as const,
        supported_orientations: ['portrait' as const],
        default_orientation: 'portrait' as const,
        default_rows_per_page: 20,
        field_slots: [],
        default_options: {
          grid_columns: 20,
          grid_rows: 20,
          box_style: 'square' as const,
          content_mode: 'blank' as const,
        },
      },
    ],
  }

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

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(mockMeta)
    vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockResolvedValue(mockPreviewData as any)
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

  it('renders live studio with header, templates list, and automatic demo preview', async () => {
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

    // Wait for async meta fetch and auto debounced preview
    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(document.body.textContent).toContain('Xuất bài tập in ấn / PDF (A4)')
    expect(document.body.textContent).toContain('Live Studio')
    expect(document.body.textContent).toContain('Luyện viết Kanji chuẩn')
    expect(document.body.textContent).toContain('Luyện viết từ vựng')
    expect(document.body.textContent).toContain('In ngay (A4)')

    // Live preview canvas content
    expect(document.body.textContent).toContain('日')
    expect(document.body.textContent).toContain('Mặt trời, ngày')
  })

  it('switches sidebar tabs between template, data, layout, and header', async () => {
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
      await new Promise((r) => setTimeout(r, 300))
    })

    // Click Tab 2: Dữ liệu & Trường
    const dataTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dữ liệu & Trường'),
    )
    expect(dataTabBtn).toBeDefined()

    await act(async () => {
      dataTabBtn?.click()
    })

    expect(document.body.textContent).toContain('Phạm vi dữ liệu')
    expect(document.body.textContent).toContain('Ánh xạ trường nguồn')

    // Click Tab 3: Bố cục & Ô chữ
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục & Ô chữ'),
    )
    expect(layoutTabBtn).toBeDefined()

    await act(async () => {
      layoutTabBtn?.click()
    })

    expect(document.body.textContent).toContain('Khổ giấy & Hướng in A4')
    expect(document.body.textContent).toContain('Kiểu đường kẻ ô')
    expect(document.body.textContent).toContain('Số ô đồ chữ (mờ)')

    // Click Tab 4: Tiêu đề & Thông tin
    const headerTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiêu đề & Thông tin'),
    )
    expect(headerTabBtn).toBeDefined()

    await act(async () => {
      headerTabBtn?.click()
    })

    expect(document.body.textContent).toContain('Tiêu đề bài tập')
    expect(document.body.textContent).toContain('Phụ đề / Hướng dẫn')
  })

  it('renders workbench page navigation and zoom controls', async () => {
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
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(document.body.textContent).toContain('Trang trước')
    expect(document.body.textContent).toContain('Trang sau')
    expect(document.body.textContent).toContain('Vừa trang')
    expect(document.body.textContent).toContain('100%')
  })

  it('switches to deck_table template without crashing and renders custom columns', async () => {
    const tablePreviewData = {
      template: {
        id: 'deck_table',
        name_vi: 'Bảng dữ liệu bộ thẻ tuỳ biến',
        category: 'table' as const,
        field_slots: [],
      },
      deck_id: 1,
      deck_name: 'JLPT N5 Core',
      options: { orientation: 'portrait' as const, rows_per_page: 15 },
      field_mapping: { custom_columns: ['Expression', 'Meaning'] },
      total_items: 1,
      total_pages: 1,
      pages: [
        {
          page_number: 1,
          total_pages: 1,
          header: {
            title: 'JLPT N5 Core - Bảng dữ liệu',
            show_student_info: true,
            show_date: true,
          },
          items: [
            {
              type: 'table_row' as const,
              note_id: '1',
              data: {
                Expression: '日本語',
                Meaning: 'Tiếng Nhật',
              },
            },
          ],
        },
      ],
      warnings: [],
    }

    vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockResolvedValue(tablePreviewData as any)

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
      await new Promise((r) => setTimeout(r, 300))
    })

    // Click template card for deck_table
    const tplCard = Array.from(document.querySelectorAll('h4')).find((h) =>
      h.textContent?.includes('Bảng dữ liệu bộ thẻ tuỳ biến'),
    )
    expect(tplCard).toBeDefined()
    await act(async () => {
      tplCard?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // By default no columns are selected -> shows helpful empty state
    expect(document.body.textContent).toContain('Chưa chọn cột nào để hiển thị')

    // Switch to Data tab and click "Tất cả"
    const dataTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dữ liệu & Trường'),
    )
    expect(dataTabBtn).toBeDefined()
    await act(async () => {
      dataTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    const selectAllBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.trim() === 'Tất cả',
    )
    expect(selectAllBtn).toBeDefined()
    await act(async () => {
      selectAllBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(document.body.textContent).toContain('日本語')
    expect(document.body.textContent).toContain('Tiếng Nhật')
  })

  it('renders auto-fit A4 toggle and extra blank rows selector in layout tab', async () => {
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
      await new Promise((r) => setTimeout(r, 300))
    })

    // Click Layout Tab
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục & Ô chữ'),
    )
    expect(layoutTabBtn).toBeDefined()
    await act(async () => {
      layoutTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    expect(document.body.textContent).toContain('Tự tính số dòng Full trang A4')
    expect(document.body.textContent).toContain('Dòng trống luyện viết bổ sung')
    expect(document.body.textContent).toContain('+1 dòng')
    expect(document.body.textContent).toContain('Điền đầy trang cuối bằng dòng trống')
  })

  it('switches to genkouyoushi template and renders essay controls', async () => {
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
      await new Promise((r) => setTimeout(r, 300))
    })

    // Find and click Genkouyoushi template card
    const genkouCard = Array.from(document.querySelectorAll('h4')).find((h) =>
      h.textContent?.includes('Genkō Yōshi') || h.textContent?.includes('400 ô'),
    )
    expect(genkouCard).toBeDefined()

    await act(async () => {
      genkouCard?.parentElement?.parentElement?.parentElement?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    // Click Tab 3: Bố cục & Ô chữ
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục & Ô chữ'),
    )
    await act(async () => {
      layoutTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    expect(document.body.textContent).toContain('Tuỳ biến Lưới bài văn Genkō Yōshi')
    expect(document.body.textContent).toContain('Trang trắng (Tập viết tay)')
    expect(document.body.textContent).toContain('400 ô (20 × 20)')
    expect(document.body.textContent).toContain('Dải đệm ngang giữa các hàng (Spacer Band)')
  })

  it('renders standalone mode without any deckId', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={null}
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(document.body.textContent).toContain('Mẫu giấy luyện viết & In ấn (A4)')
    expect(document.body.textContent).toContain('Mẫu giấy độc lập (Không cần deck)')
    expect(document.body.textContent).toContain('Tự do luyện viết')

    // Click Tab 2: Dữ liệu & Trường
    const dataTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Dữ liệu & Trường'),
    )
    await act(async () => {
      dataTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    expect(document.body.textContent).toContain('Mẫu giấy in độc lập')
    expect(document.body.textContent).toContain('Không cần chọn Deck')
  })

  it('renders mobile view with segmented switcher and mobile action buttons', async () => {
    // Set window.innerWidth to mobile size
    const originalInnerWidth = window.innerWidth
    window.innerWidth = 375

    try {
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
        await new Promise((r) => setTimeout(r, 300))
      })

      // Check Mobile Header switcher
      const buttons = Array.from(document.querySelectorAll('button'))
      const mobileControlsBtn = buttons.find((b) => b.textContent?.includes('Cấu hình'))
      const mobilePreviewBtn = buttons.find((b) => b.textContent?.includes('Xem bản in'))

      expect(mobileControlsBtn).toBeDefined()
      expect(mobilePreviewBtn).toBeDefined()

      // Check mobile zoom / fit and download buttons
      expect(document.body.textContent).toContain('Vừa trang')
      expect(document.body.textContent).toContain('Tải file')

      // Switch to controls
      await act(async () => {
        mobileControlsBtn?.click()
      })

      await act(async () => {
        await new Promise((r) => setTimeout(r, 100))
      })

      // In controls mode, the bottom quick preview button should exist
      const quickPreviewBtn = Array.from(document.querySelectorAll('button')).find(
        (b) => b.textContent?.trim() === 'Xem bản in',
      )
      expect(quickPreviewBtn).toBeDefined()
    } finally {
      window.innerWidth = originalInnerWidth
    }
  })
})



// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DeckWorksheetModal } from './components/DeckWorksheetModal'
import * as worksheetApi from './api'
import * as clientApi from '@/shared/api/client'
import { saveWorksheetPreset } from './utils/worksheetStorage'
import type { DeckWorksheetMeta } from './types'

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
        sample_values: {
          Expression: '食べる',
          Reading: 'たべる',
          Meaning: 'Ăn',
        },
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
        id: 'kanji_compact',
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
          initialStep="studio"
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
    expect(document.body.textContent).toContain('In / Lưu PDF')

    // Live preview canvas content (reading and meaning hidden by default)
    expect(document.body.textContent).toContain('日')
    expect(document.body.textContent).not.toContain('Mặt trời, ngày')
  })

  it('switches sidebar tabs between template, data, layout, and header', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
          initialStep="studio"
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
          initialStep="studio"
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
          initialStep="studio"
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
          initialStep="studio"
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
          initialStep="studio"
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
          initialStep="studio"
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
            initialStep="studio"
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

      // Check mobile zoom / fit and the single native print action
      expect(document.body.textContent).toContain('Vừa trang')
      expect(document.body.textContent).toContain('In / Lưu PDF')
      expect(document.body.textContent).not.toContain('Tải file PDF')
      expect(document.body.textContent).not.toContain('Tab mới')

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

  it('renders desktop/laptop responsive dialog with sm:max-w-none to prevent phone frame constraint', async () => {
    const originalInnerWidth = window.innerWidth
    window.innerWidth = 1280

    try {
      await act(async () => {
        root?.render(
          <DeckWorksheetModal
            open={true}
            onOpenChange={vi.fn()}
            deckId={1}
            deckName="JLPT N5 Core"
            initialStep="studio"
          />,
        )
      })

      await act(async () => {
        await new Promise((r) => setTimeout(r, 300))
      })

      const dialogContent = document.querySelector('[data-slot="dialog-content"]')
      expect(dialogContent).toBeDefined()
      expect(dialogContent?.className).toContain('sm:max-w-none')
      expect(dialogContent?.className).not.toContain('sm:max-w-sm')

      // Desktop header should be present with Live Studio badge
      expect(document.body.textContent).toContain('Live Studio')
      expect(document.body.textContent).toContain('Xuất bài tập in ấn / PDF (A4)')
    } finally {
      window.innerWidth = originalInnerWidth
    }
  })

  it('handles detected Chinese deck locale and allows changing stroke language / dataset', async () => {
    const chineseMeta = {
      ...mockMeta,
      deck_id: 1619,
      deck_name: 'HSK 1 Bài 4',
      detected_locale: 'zh' as const,
    }
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(chineseMeta)

    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1619}
          deckName="HSK 1 Bài 4"
          initialStep="studio"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Switch to Layout tab (Tab 3: Bố cục & Ô chữ)
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

    // Verify auto-detected badge
    expect(document.body.textContent).toContain('Tự động: Tiếng Trung')

    // Verify select element has zh selected
    const selectEl = Array.from(document.querySelectorAll('select')).find((s) =>
      Array.from(s.options).some((opt) => opt.value === 'zh'),
    ) as HTMLSelectElement | undefined
    expect(selectEl).toBeDefined()
    expect(selectEl?.value).toBe('zh')

    // Change select to Japanese (ja)
    await act(async () => {
      if (selectEl) {
        selectEl.value = 'ja'
        selectEl.dispatchEvent(new Event('change', { bubbles: true }))
      }
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          locale: 'ja',
        }),
      }),
    )
  })

  it('supports toggling stroke numbers on and off in layout tab', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
          initialStep="studio"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Switch to Layout tab
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục & Ô chữ'),
    )
    await act(async () => {
      layoutTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    // Find stroke numbers toggle checkbox
    const strokeNumLabel = Array.from(document.querySelectorAll('label')).find((l) =>
      l.textContent?.includes('Hiện số thứ tự nét 1, 2, 3...'),
    )
    expect(strokeNumLabel).toBeDefined()
    const checkbox = strokeNumLabel?.querySelector('input[type="checkbox"]') as HTMLInputElement | null
    expect(checkbox).toBeDefined()
    expect(checkbox?.checked).toBe(true)

    // Uncheck it
    await act(async () => {
      checkbox?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          show_stroke_numbers: false,
        }),
      }),
    )
  })

  it('switches between Chinese and Japanese via the prominent sidebar top switcher', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
          initialStep="studio"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Find the Chinese button in the prominent top switcher
    const zhButton = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếng Trung (Giản thể)'),
    )
    expect(zhButton).toBeDefined()

    // Click Chinese button
    await act(async () => {
      zhButton?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          locale: 'zh',
        }),
      }),
    )

    // Click Japanese button
    const jaButton = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếng Nhật') && b.textContent?.includes('🇯🇵'),
    )
    expect(jaButton).toBeDefined()

    await act(async () => {
      jaButton?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        options: expect.objectContaining({
          locale: 'ja',
        }),
      }),
    )
  })

  it('preserves layout parameter isolation when switching between templates and renders vocab controls', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={() => {}}
          deckId={1}
          deckName="JLPT N5 Core"
          initialStep="studio"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Switch to layout tab
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Bố cục') || b.textContent?.includes('Bố cục & Ô chữ'),
    )
    expect(layoutTabBtn).toBeDefined()

    await act(async () => {
      layoutTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    // Verify Quick Presets section is visible
    expect(document.body.textContent).toContain('Bố cục mẫu 1-chạm')
    expect(document.body.textContent).toContain('Mặc định tối ưu')

    // Click "Tiết kiệm giấy" preset for kanji
    const ecoPresetBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiết kiệm giấy'),
    )
    expect(ecoPresetBtn).toBeDefined()

    await act(async () => {
      ecoPresetBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: 'kanji_compact',
        options: expect.objectContaining({
          box_size: 28,
          trace_count: 1,
          practice_count: 8,
        }),
      }),
    )

    // Switch to Template tab and select Vocab Writing
    const templateTabBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Mẫu') || b.textContent?.includes('Mẫu bài tập'),
    )
    expect(templateTabBtn).toBeDefined()

    await act(async () => {
      templateTabBtn?.click()
    })

    const vocabTplCard = Array.from(document.querySelectorAll('h4')).find((h) =>
      h.textContent?.includes('Luyện viết từ vựng'),
    )
    expect(vocabTplCard).toBeDefined()

    await act(async () => {
      vocabTplCard?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Switch to layout tab again
    await act(async () => {
      layoutTabBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100))
    })

    // Verify vocab writing controls are rendered
    expect(document.body.textContent).toContain('Tuỳ biến Bảng Luyện viết Từ vựng')
    expect(document.body.textContent).toContain('Kiểu vùng luyện viết')
    expect(document.body.textContent).toContain('Ô vuông liền')
    expect(document.body.textContent).toContain('Dòng kẻ viết')
    expect(document.body.textContent).toContain('Cột Cách đọc')

    // Switch back to kanji_stroke template
    await act(async () => {
      templateTabBtn?.click()
    })

    const kanjiTplCard = Array.from(document.querySelectorAll('h4')).find((h) =>
      h.textContent?.includes('Luyện viết Kanji chuẩn'),
    )
    expect(kanjiTplCard).toBeDefined()

    await act(async () => {
      kanjiTplCard?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Verify kanji_compact retained its 28px box_size and 8 practice boxes from earlier
    expect(worksheetApi.generateWorksheetPreview).toHaveBeenCalledWith(
      expect.objectContaining({
        template_id: 'kanji_compact',
        options: expect.objectContaining({
          box_size: 28,
          practice_count: 8,
        }),
      }),
    )
  })

  it('defaults show_reading, show_meaning, and show_source_word to off for kanji practice and allows toggling them', async () => {
    await act(async () => {
      root?.render(
        <DeckWorksheetModal
          open={true}
          onOpenChange={vi.fn()}
          deckId={1}
          deckName="JLPT N5 Core"
          initialStep="studio"
        />,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Click Tab 3: Bố cục & Ô chữ
    const layoutTabBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục & Ô chữ'),
    )
    await act(async () => {
      layoutTabBtn?.click()
    })

    // Verify checkboxes exist
    expect(document.body.textContent).toContain('Hiện Âm đọc')
    expect(document.body.textContent).toContain('Hiện Ý nghĩa')
    expect(document.body.textContent).toContain('Hiện Từ ví dụ')

    // Find the checkboxes
    const labels = Array.from(document.querySelectorAll('label'))
    const readLabel = labels.find((l) => l.textContent?.includes('Hiện Âm đọc'))
    const meanLabel = labels.find((l) => l.textContent?.includes('Hiện Ý nghĩa'))
    const exampleLabel = labels.find((l) => l.textContent?.includes('Hiện Từ ví dụ'))

    const readInput = readLabel?.querySelector('input[type="checkbox"]') as HTMLInputElement
    const meanInput = meanLabel?.querySelector('input[type="checkbox"]') as HTMLInputElement
    const exampleInput = exampleLabel?.querySelector('input[type="checkbox"]') as HTMLInputElement

    expect(readInput.checked).toBe(false)
    expect(meanInput.checked).toBe(false)
    expect(exampleInput.checked).toBe(false)

    // Toggle Hiện Ý nghĩa ON
    await act(async () => {
      meanInput.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Now meaning should be visible in preview
    expect(document.body.textContent).toContain('Mặt trời, ngày')
  })

  it('supports toggling page_fill_mode between balanced_stretch and max_density in layout tab', async () => {
    await act(async () => {
      root!.render(<DeckWorksheetModal open={true} onOpenChange={() => {}} deckId={1} initialStep="studio" />)
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 400))
    })

    // Click on Layout tab
    const layoutTab = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục'),
    )
    expect(layoutTab).toBeDefined()

    await act(async () => {
      layoutTab!.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Find and click "Tiết kiệm giấy" button in Page Fill Mode
    const maxDensityBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('⚡ Tiết kiệm giấy') && b.textContent?.includes('phủ kín tối đa số từ'),
    )
    expect(maxDensityBtn).toBeDefined()

    await act(async () => {
      maxDensityBtn!.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Verify generateWorksheetPreview was called with page_fill_mode: 'max_density'
    const lastCall = vi.mocked(worksheetApi.generateWorksheetPreview).mock.calls.at(-1)?.[0]
    expect(lastCall?.options?.page_fill_mode).toBe('max_density')
  })

  it('highlights quick preset button as selected with active styling when clicked', async () => {
    await act(async () => {
      root!.render(<DeckWorksheetModal open={true} onOpenChange={() => {}} deckId={1} initialStep="studio" />)
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 400))
    })

    // Click on Layout tab
    const layoutTab = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Bố cục'),
    )
    expect(layoutTab).toBeDefined()

    await act(async () => {
      layoutTab!.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Find the quick preset "⚡ Tiết kiệm giấy" in "Bố cục mẫu 1-chạm"
    const presetBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('⚡ Tiết kiệm giấy') && b.textContent?.includes('Ô 28px, 1 mờ, 8 viết'),
    )
    expect(presetBtn).toBeDefined()

    // Click the preset
    await act(async () => {
      presetBtn!.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Verify button has active primary styling (border-primary and bg-primary/10)
    expect(presetBtn?.className).toContain('border-primary')
    expect(presetBtn?.className).toContain('bg-primary/10')
  })
})

describe('DeckWorksheetModal Wizard Flow', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let queryClient: QueryClient

  const mockMeta: DeckWorksheetMeta = {
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    total_notes: 30,
    note_types: [
      {
        id: 'nt1',
        name: 'Vocabulary Note',
        fields: ['Expression', 'Reading', 'Meaning'],
        note_count: 30,
        sample_values: {
          Expression: '食べる',
          Reading: 'たべる',
          Meaning: 'Ăn',
        },
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
        id: 'kanji_compact',
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
        id: 'genkouyoushi',
        name_vi: 'Trang trắng (Tập viết tay)',
        name_en: 'Blank Essay Sheet',
        description_vi: 'Giấy kẻ ô trống Genkō Yōshi.',
        description_en: 'Blank paper.',
        category: 'essay' as const,
        supported_orientations: ['portrait' as const],
        default_orientation: 'portrait' as const,
        default_rows_per_page: 20,
        field_slots: [],
        default_options: {},
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
    pages: [],
    warnings: [],
  }

  beforeEach(() => {
    localStorage.clear()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(mockMeta)
    vi.spyOn(worksheetApi, 'generateWorksheetPreview').mockResolvedValue(mockPreviewData as any)
    vi.spyOn(clientApi, 'apiRequest').mockImplementation(async (path: string) => {
      if (path === '/api/browse/decks') {
        return {
          decks: [
            { id: 1, name: 'JLPT N5 Core', parent_id: null, counts: { total: 30 } },
            { id: 2, name: 'JLPT N4 Mixed', parent_id: null, counts: { total: 40 } },
          ],
        }
      }
      return {}
    })
  })

  afterEach(() => {
    if (root && container) {
      act(() => {
        root?.unmount()
      })
      container.remove()
    }
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('starts at Step 1 (deck tree) when deckId is null, and allows selecting standalone blank sheet', async () => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={null} />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Should display step 1 deck tree selection
    expect(document.body.textContent).toContain('Bước 1: Chọn bộ thẻ để xuất bài tập')
    expect(document.body.textContent).toContain('Tạo mẫu giấy in tự do (Không cần thẻ học)')

    // Click standalone button
    const standaloneBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Chọn mẫu tự do'),
    )
    expect(standaloneBtn).toBeDefined()

    await act(async () => {
      standaloneBtn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Now should be on Step 3: Chọn bài tập (standalone templates)
    expect(document.body.textContent).toContain('Chọn loại bài tập')
    expect(document.body.textContent).toContain('Trang trắng (Tập viết tay)')
  })

  it('skips Step 1 and lands directly on Step 2 (mapping) when valid deckId is provided', async () => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={1} deckName="JLPT N5 Core" />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Step 2 should be active
    expect(document.body.textContent).toContain('Ánh xạ dữ liệu')
    expect(document.body.textContent).toContain('Chữ Hán / Từ vựng chính')
    expect(document.body.textContent).toContain('Giá trị mẫu trên thẻ:"食べる"')
    expect(document.body.textContent).toContain('Tiếp tục: Chọn mẫu bài tập')
    expect(worksheetApi.generateWorksheetPreview).not.toHaveBeenCalled()
  })

  it('blocks proceeding if deck contains multiple note types', async () => {
    const mixedMeta: DeckWorksheetMeta = {
      ...mockMeta,
      has_mixed_note_types: true,
      note_types: [
        { id: 'nt1', name: 'Kanji Note', fields: ['Kanji', 'Onyomi'], note_count: 20 },
        { id: 'nt2', name: 'Grammar Note', fields: ['Pattern', 'Meaning'], note_count: 20 },
      ],
    }
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(mixedMeta)

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={2} deckName="JLPT N4 Mixed" />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Expect warning alert and multiple note types block
    expect(document.body.textContent).toContain('Không thể tiếp tục: Bộ thẻ chứa 2 loại thẻ khác nhau')
    expect(document.body.textContent).toContain('bộ thẻ phải đồng nhất duy nhất 1 loại thẻ (Note Type)')

    // Find the Next button (Tiếp tục: Ánh xạ dữ liệu in step 1)
    const nextBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Ánh xạ dữ liệu'),
    )
    expect(nextBtn).toBeDefined()
    expect(nextBtn?.hasAttribute('disabled')).toBe(true)
  })

  it('allows progressing through Step 2 -> Step 3 -> Step 4', async () => {
    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={1} deckName="JLPT N5 Core" />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Step 2 -> Step 3
    const toStep3Btn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Chọn mẫu bài tập'),
    )
    expect(toStep3Btn).toBeDefined()

    await act(async () => {
      toStep3Btn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 200))
    })

    // Step 3 is rendered
    expect(document.body.textContent).toContain('Chọn loại bài tập')
    expect(document.body.textContent).toContain('Luyện viết Kanji chuẩn')

    // Step 3 -> Step 4
    const toStep4Btn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Tiếp tục: Cấu hình & In ấn'),
    )
    expect(toStep4Btn).toBeDefined()

    await act(async () => {
      toStep4Btn?.click()
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Step 4 Studio is rendered
    expect(document.body.textContent).toContain('Live Studio')
    expect(document.body.textContent).toContain('Xuất bài tập in ấn / PDF (A4)')
  })

  it('auto-populates saved preset from localStorage', async () => {
    saveWorksheetPreset('nt1', {
      fieldMapping: { kanji: 'Reading' },
      templateId: 'vocab_writing',
    })

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={1} deckName="JLPT N5 Core" />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Verify preset notification badge
    expect(document.body.textContent).toContain('Đã nạp thiết lập đã lưu')
  })

  it('renders mapping step without crashing when sample_values contains array or non-string values', async () => {
    const metaWithArraySample = {
      ...mockMeta,
      note_types: [
        {
          ...mockMeta.note_types[0],
          sample_values: {
            Expression: '食べる',
            Reading: 'たべる',
            Meaning: ['Ăn', 'Dùng bữa'] as any,
            Audio: '[sound:taberu.mp3]',
            Count: 42 as any,
          },
        },
      ],
    }
    vi.spyOn(worksheetApi, 'fetchDeckWorksheetMeta').mockResolvedValue(metaWithArraySample)

    await act(async () => {
      root?.render(
        <QueryClientProvider client={queryClient}>
          <DeckWorksheetModal open={true} onOpenChange={vi.fn()} deckId={1} deckName="JLPT N5 Core" />
        </QueryClientProvider>,
      )
    })

    await act(async () => {
      await new Promise((r) => setTimeout(r, 300))
    })

    // Mapping step should render safely without throwing "r.endsWith is not a function"
    expect(document.body.textContent).toContain('Bước 2: Ánh xạ trường dữ liệu từ thẻ học')
    expect(document.body.textContent).toContain('Ăn')
  })
})


// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'
import { serializeWorksheetToHtml } from './serializeWorksheetToHtml'
import type { WorksheetPreviewResponse } from '../types'

describe('serializeWorksheetToHtml', () => {
  const mockPreviewData: WorksheetPreviewResponse = {
    template: {
      id: 'kanji_compact',
      name_vi: 'Luyện viết Kanji chuẩn',
      name_en: 'Kanji Stroke Practice',
      description_vi: 'Mẫu chữ Hán chuẩn với sơ đồ nét.',
      description_en: 'Standard Kanji practice.',
      category: 'kanji',
      supported_orientations: ['portrait', 'landscape'],
      default_orientation: 'portrait',
      default_rows_per_page: 5,
      field_slots: [],
      default_options: {},
    },
    deck_id: 1,
    deck_name: 'JLPT N5 Core',
    options: {
      orientation: 'portrait',
      margin: 'compact',
      rows_per_page: 5,
      box_size: 36,
      trace_count: 2,
      practice_count: 4,
    },
    field_mapping: { kanji: 'Expression' },
    total_items: 1,
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
            type: 'kanji',
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

  it('serializes a single-page worksheet into standalone HTML with inline styles', async () => {
    const html = await serializeWorksheetToHtml(mockPreviewData)

    expect(html).toContain('<!DOCTYPE html>')
    expect(html).toContain('<html lang="ja">')
    expect(html).toContain('@page')
    expect(html).toContain('210mm 297mm')
    expect(html).toContain('sheet-page')
    expect(html).toContain('JLPT N5 Core - Bài tập')
    expect(html).toContain('日')
    expect(html).toContain('Flama Worksheet')
  })

  it('handles landscape orientation correctly', async () => {
    const landscapeData: WorksheetPreviewResponse = {
      ...mockPreviewData,
      options: {
        ...mockPreviewData.options,
        orientation: 'landscape',
      },
    }

    const html = await serializeWorksheetToHtml(landscapeData)

    expect(html).toContain('297mm 210mm')
  })

  it('serializes multiple pages with proper page-break structure', async () => {
    const multiPageData: WorksheetPreviewResponse = {
      ...mockPreviewData,
      total_pages: 2,
      pages: [
        mockPreviewData.pages[0],
        {
          ...mockPreviewData.pages[0],
          page_number: 2,
        },
      ],
    }

    const html = await serializeWorksheetToHtml(multiPageData)

    // Should contain 2 sheet-page elements
    const matches = html.match(/class="[^"]*sheet-page[^"]*"/g)
    expect(matches).not.toBeNull()
    expect(matches!.length).toBe(2)
  })

  it('throws an error if previewData has no pages', async () => {
    const emptyData: WorksheetPreviewResponse = {
      ...mockPreviewData,
      pages: [],
    }

    await expect(serializeWorksheetToHtml(emptyData)).rejects.toThrow('No pages to serialize')
  })
})

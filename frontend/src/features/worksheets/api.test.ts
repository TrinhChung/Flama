import { describe, expect, it, vi } from 'vitest'
import {
  fetchDeckWorksheetMeta,
  fetchWorksheetTemplates,
  generateWorksheetPreview,
  renderWorksheetHtml,
} from './api'
import * as client from '@/shared/api/client'

describe('Worksheet API Client', () => {
  it('fetches worksheet templates', async () => {
    const mockTemplates = [
      { id: 'kanji_stroke', name_vi: 'Luyện viết Kanji chuẩn' },
    ]
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValueOnce({ templates: mockTemplates })

    const res = await fetchWorksheetTemplates()
    expect(spy).toHaveBeenCalledWith('/api/worksheets/templates')
    expect(res).toEqual(mockTemplates)
  })

  it('fetches deck worksheet meta', async () => {
    const mockMeta = {
      deck_id: 123,
      deck_name: 'JLPT N5',
      total_notes: 50,
      note_types: [],
      suggested_mappings: { kanji: 'Expression' },
      templates: [],
    }
    const spy = vi.spyOn(client, 'apiRequest').mockResolvedValueOnce(mockMeta)

    const res = await fetchDeckWorksheetMeta(123)
    expect(spy).toHaveBeenCalledWith('/api/decks/123/worksheets/meta')
    expect(res.deck_id).toBe(123)
  })

  it('generates worksheet preview', async () => {
    const mockPreview = {
      template: { id: 'kanji_stroke' },
      total_items: 10,
      total_pages: 2,
      pages: [],
      warnings: [],
    }
    const spy = vi.spyOn(client, 'apiJson').mockResolvedValueOnce(mockPreview)

    const payload = {
      deck_id: 123,
      template_id: 'kanji_stroke',
      field_mapping: { kanji: 'Expression' },
    }
    const res = await generateWorksheetPreview(payload as any)
    expect(spy).toHaveBeenCalledWith('/api/worksheets/preview', 'POST', payload)
    expect(res.total_items).toBe(10)
  })

  it('renders printable HTML', async () => {
    const mockHtml = '<!DOCTYPE html><html><body>Test</body></html>'
    const spy = vi.spyOn(client, 'apiJson').mockResolvedValueOnce({
      html: mockHtml,
      filename: 'worksheet_kanji_stroke.html',
    })

    const payload = {
      deck_id: 123,
      template_id: 'kanji_stroke',
      field_mapping: { kanji: 'Expression' },
    }
    const res = await renderWorksheetHtml(payload as any)
    expect(spy).toHaveBeenCalledWith(
      '/api/worksheets/render-html?format=json',
      'POST',
      payload,
    )
    expect(res).toBe(mockHtml)
  })
})

import { beforeEach, describe, expect, it, vi } from 'vitest'

const { apiRequest, apiJson } = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  apiJson: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({
  apiRequest,
  apiJson,
}))

import {
  cardTemplateQueryKeys,
  createNoteTypeTemplate,
  deleteNoteTypeTemplate,
  fetchDeckCardTypes,
  fetchNoteTypeTemplates,
  renameNoteTypeTemplate,
} from '../index'

describe('cardTemplateApi and queryKeys', () => {
  beforeEach(() => {
    apiRequest.mockReset()
    apiJson.mockReset()
  })

  describe('fetchNoteTypeTemplates', () => {
    it('calls apiRequest with properly encoded noteTypeId and returns templates response', async () => {
      const mockResponse = {
        items: [
          {
            id: 'tpl-1',
            note_type_id: 'nt/1',
            name: 'Card 1',
            front_html: '{{Front}}',
            back_html: '{{Back}}',
            shared_css: '',
            position: 0,
            is_default: true,
            updated_at: null,
            note_count: 5,
          },
        ],
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result = await fetchNoteTypeTemplates('nt/1')
      expect(result).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith('/api/note-types/nt%2F1/templates', {
        signal: undefined,
      })
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({ items: [] })

      await fetchNoteTypeTemplates('nt-2', controller.signal)
      expect(apiRequest).toHaveBeenCalledWith('/api/note-types/nt-2/templates', {
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Network error'))
      await expect(fetchNoteTypeTemplates('nt-1')).rejects.toThrow('Network error')
    })
  })

  describe('fetchDeckCardTypes', () => {
    it('calls apiRequest with deckId and include_counts=1 query parameter', async () => {
      const mockResponse = {
        schema_version: 'study-scope-compositions.v2',
        scope_type: 'deck',
        scope_id: '42',
        cardinality: 'one',
        default_composition_id: 'comp-1',
        groups: [],
        compositions: [],
        note_counts: { 'comp-1': 10 },
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result = await fetchDeckCardTypes(42)
      expect(result).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/study/scopes/deck/42/compositions?include_counts=1',
        { signal: undefined },
      )
    })

    it('encodes string deckId and forwards AbortSignal', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({ compositions: [] })

      await fetchDeckCardTypes('deck/abc', controller.signal)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/study/scopes/deck/deck%2Fabc/compositions?include_counts=1',
        { signal: controller.signal },
      )
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Forbidden'))
      await expect(fetchDeckCardTypes(42)).rejects.toThrow('Forbidden')
    })
  })

  describe('createNoteTypeTemplate', () => {
    it('calls apiJson with POST and provided body', async () => {
      const mockCreated = {
        id: 'tpl-new',
        note_type_id: 'nt1',
        name: 'Card 2',
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '',
        position: 1,
        is_default: false,
        updated_at: null,
      }
      apiJson.mockResolvedValueOnce(mockCreated)

      const payload = { name: 'Card 2', front_html: '{{Front}}' }
      const result = await createNoteTypeTemplate('nt1', payload)
      expect(result).toBe(mockCreated)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt1/templates',
        'POST',
        payload,
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Invalid payload'))
      await expect(createNoteTypeTemplate('nt1', {})).rejects.toThrow('Invalid payload')
    })
  })

  describe('renameNoteTypeTemplate', () => {
    it('calls apiJson with PATCH and strictly { name } body without extra keys', async () => {
      const mockUpdated = {
        id: 't1',
        note_type_id: 'nt1',
        name: 'Mới',
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '',
        position: 0,
        is_default: true,
        updated_at: '2026-10-05T00:00:00Z',
      }
      apiJson.mockResolvedValueOnce(mockUpdated)

      const result = await renameNoteTypeTemplate('nt/1', 't/1', 'Mới')
      expect(result).toBe(mockUpdated)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/templates/t%2F1',
        'PATCH',
        { name: 'Mới' },
      )
      const callBody = apiJson.mock.calls[0][2]
      expect(Object.keys(callBody)).toEqual(['name'])
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Rename conflict'))
      await expect(renameNoteTypeTemplate('nt1', 't1', 'Mới')).rejects.toThrow('Rename conflict')
    })
  })

  describe('deleteNoteTypeTemplate', () => {
    it('calls apiJson with DELETE and exactly 2 arguments (no body)', async () => {
      apiJson.mockResolvedValueOnce({ success: true })

      const result = await deleteNoteTypeTemplate('nt/1', 't/1')
      expect(result).toEqual({ success: true })
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/templates/t%2F1',
        'DELETE',
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Cannot delete default template'))
      await expect(deleteNoteTypeTemplate('nt1', 't1')).rejects.toThrow('Cannot delete default template')
    })
  })

  describe('cardTemplateQueryKeys', () => {
    it('generates noteTypeTemplates query key tuple', () => {
      expect(cardTemplateQueryKeys.noteTypeTemplates('nt-42')).toEqual([
        'card-template',
        'note-type-templates',
        'nt-42',
      ])
    })

    it('generates deckCardTypes query key tuple converting deckId to string', () => {
      expect(cardTemplateQueryKeys.deckCardTypes(42)).toEqual([
        'card-template',
        'deck-card-types',
        '42',
      ])
      expect(cardTemplateQueryKeys.deckCardTypes('42')).toEqual([
        'card-template',
        'deck-card-types',
        '42',
      ])
    })
  })
})

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
  fetchTemplateVersion,
  fetchTemplateVersions,
  renameNoteTypeTemplate,
  restoreTemplateVersion,
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

  describe('fetchTemplateVersions', () => {
    it('calls apiRequest with properly encoded templateId and returns version list', async () => {
      const mockResponse = {
        schema_version: 'template-versions.v2',
        template_id: 'tpl/1',
        current_version_id: 'ver-1',
        items: [
          {
            id: 'ver-1',
            template_id: 'tpl/1',
            version_no: 1,
            content_hash: 'abc123hash',
            change_note: 'initial',
            origin: 'create',
            created_at: '2026-10-06T12:00:00Z',
            created_by: { id: 1, username: 'tester' },
            is_current: true,
          },
        ],
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result = await fetchTemplateVersions('tpl/1')
      expect(result).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl%2F1/versions', {
        signal: undefined,
      })
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({
        schema_version: 'template-versions.v2',
        template_id: 'tpl-1',
        current_version_id: null,
        items: [],
      })

      await fetchTemplateVersions('tpl-1', controller.signal)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl-1/versions', {
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Failed to fetch versions'))
      await expect(fetchTemplateVersions('tpl-1')).rejects.toThrow('Failed to fetch versions')
    })
  })

  describe('fetchTemplateVersion', () => {
    it('calls apiRequest with properly encoded templateId and versionId and returns version detail', async () => {
      const mockResponse = {
        id: 'ver/1',
        template_id: 'tpl/1',
        version_no: 1,
        content_hash: 'abc123hash',
        change_note: 'initial commit',
        origin: 'create',
        created_at: '2026-10-06T12:00:00Z',
        created_by: { id: 1, username: 'tester' },
        is_current: true,
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '.card { color: red; }',
        input_schema: [],
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result = await fetchTemplateVersion('tpl/1', 'ver/1')
      expect(result).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl%2F1/versions/ver%2F1', {
        signal: undefined,
      })
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({
        id: 'ver-2',
        template_id: 'tpl-2',
        version_no: 2,
        content_hash: 'def456hash',
        change_note: '',
        origin: 'edit',
        created_at: '2026-10-06T13:00:00Z',
        created_by: null,
        is_current: false,
        front_html: '',
        back_html: '',
        shared_css: '',
        input_schema: [],
      })

      await fetchTemplateVersion('tpl-2', 'ver-2', controller.signal)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl-2/versions/ver-2', {
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Version not found'))
      await expect(fetchTemplateVersion('tpl-1', 'ver-404')).rejects.toThrow('Version not found')
    })
  })

  describe('restoreTemplateVersion', () => {
    const mockRestored = {
      id: 'tpl/1',
      note_type_id: 'nt1',
      name: 'Default',
      front_html: '{{Front}}',
      back_html: '{{Back}}',
      shared_css: '',
      position: 0,
      is_default: true,
      updated_at: '2026-10-06T14:00:00Z',
      current_version_id: 'ver-new',
    }

    it('calls apiJson with POST and body containing change_note when provided', async () => {
      apiJson.mockResolvedValueOnce(mockRestored)

      const result = await restoreTemplateVersion('tpl/1', 'ver/1', 'Khôi phục bản cũ')
      expect(result).toBe(mockRestored)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl%2F1/versions/ver%2F1/restore',
        'POST',
        { change_note: 'Khôi phục bản cũ' },
      )
    })

    it('calls apiJson with empty object body when changeNote is omitted', async () => {
      apiJson.mockResolvedValueOnce(mockRestored)

      const result = await restoreTemplateVersion('tpl-1', 'ver-1')
      expect(result).toBe(mockRestored)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl-1/versions/ver-1/restore',
        'POST',
        {},
      )
    })

    it('calls apiJson with empty object body when changeNote is empty string', async () => {
      apiJson.mockResolvedValueOnce(mockRestored)

      const result = await restoreTemplateVersion('tpl-1', 'ver-1', '')
      expect(result).toBe(mockRestored)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl-1/versions/ver-1/restore',
        'POST',
        {},
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Restore failed'))
      await expect(restoreTemplateVersion('tpl-1', 'ver-1')).rejects.toThrow('Restore failed')
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

    it('generates templateVersions query key tuple', () => {
      expect(cardTemplateQueryKeys.templateVersions('tpl-123')).toEqual([
        'card-template',
        'versions',
        'tpl-123',
      ])
    })

    it('generates templateVersion query key tuple', () => {
      expect(cardTemplateQueryKeys.templateVersion('tpl-123', 'ver-456')).toEqual([
        'card-template',
        'versions',
        'tpl-123',
        'ver-456',
      ])
    })
  })
})

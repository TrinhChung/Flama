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
  attachLibraryTemplate,
  archiveLibraryTemplate,
  cardTemplateQueryKeys,
  createLibraryTemplate,
  createNoteTypeTemplate,
  deleteNoteTypeTemplate,
  duplicateLibraryTemplate,
  fetchDeckCardTypes,
  fetchLibraryTemplate,
  fetchNoteTypeTemplates,
  fetchStudyTemplateInputs,
  fetchStudyTemplatePreset,
  fetchTemplateApplications,
  fetchTemplateLibrary,
  fetchTemplateVersion,
  fetchTemplateVersions,
  previewLibraryTemplate,
  renameNoteTypeTemplate,
  restoreTemplateVersion,
  retireTemplateApplication,
  saveStudyTemplatePreset,
  updateLibraryTemplate,
  updateTemplateApplication,
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

  describe('fetchTemplateLibrary', () => {
    it('calls apiRequest with /api/card-templates and no query string when params are empty or omitted', async () => {
      const mockResponse = {
        schema_version: 'template-library.v2',
        items: [],
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result1 = await fetchTemplateLibrary()
      expect(result1).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates', { signal: undefined })

      apiRequest.mockResolvedValueOnce(mockResponse)
      const result2 = await fetchTemplateLibrary({})
      expect(result2).toBe(mockResponse)
      expect(apiRequest).toHaveBeenLastCalledWith('/api/card-templates', { signal: undefined })
    })

    it('serializes query parameters strictly in order: q, group, category, include_archived', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({
        category: 'grammar',
        include_archived: true,
        q: 'search_term',
        group: 'mine',
      })

      expect(apiRequest).toHaveBeenCalledWith(
        '/api/card-templates?q=search_term&group=mine&category=grammar&include_archived=true',
        { signal: undefined },
      )
    })

    it('omits empty string, undefined, and false parameters', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({
        q: '',
        group: undefined,
        category: '',
        include_archived: false,
      })

      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates', { signal: undefined })
    })

    it('serializes include_archived: true as literal string "true"', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({ include_archived: true })

      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates?include_archived=true', {
        signal: undefined,
      })
    })

    it('preserves untrimmed whitespace in q parameter', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({ q: '   ' })

      const calledUrl: string = apiRequest.mock.calls[0][0]
      expect(calledUrl).toBe('/api/card-templates?q=+++')
    })

    it('encodes Japanese characters in q parameter', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({ q: '日本語' })

      expect(apiRequest).toHaveBeenCalledWith(
        '/api/card-templates?q=%E6%97%A5%E6%9C%AC%E8%AA%9E',
        { signal: undefined },
      )
    })

    it('encodes literal % and _ in q parameter', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({ q: '50%_discount' })

      expect(apiRequest).toHaveBeenCalledWith(
        '/api/card-templates?q=50%25_discount',
        { signal: undefined },
      )
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-library.v2', items: [] })

      await fetchTemplateLibrary({ group: 'all' }, controller.signal)

      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates?group=all', {
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Failed to fetch library'))
      await expect(fetchTemplateLibrary()).rejects.toThrow('Failed to fetch library')
    })
  })

  describe('fetchLibraryTemplate', () => {
    it('calls apiRequest with encoded template ID', async () => {
      const mockDetail = {
        id: 'tpl/1',
        owner_user_id: 1,
        name: 'Template 1',
        description: 'Desc',
        primary_category: null,
        origin: 'authored',
        source_template_id: null,
        source_version_id: null,
        current_version_id: 'ver-1',
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '',
        input_schema: [],
        archived_at: null,
        created_at: null,
        updated_at: null,
        application_count: 1,
        note_type_count: 1,
        applications: [],
      }
      apiRequest.mockResolvedValueOnce(mockDetail)

      const result = await fetchLibraryTemplate('tpl/1')
      expect(result).toBe(mockDetail)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl%2F1', {
        signal: undefined,
      })
    })

    it('encodes special characters in template ID (path traversal, query, fragment)', async () => {
      apiRequest.mockResolvedValueOnce({} as any)

      await fetchLibraryTemplate('tpl?query=1#frag')
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl%3Fquery%3D1%23frag', {
        signal: undefined,
      })
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({} as any)

      await fetchLibraryTemplate('tpl-1', controller.signal)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl-1', {
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Template not found'))
      await expect(fetchLibraryTemplate('tpl-404')).rejects.toThrow('Template not found')
    })
  })

  describe('createLibraryTemplate', () => {
    it('calls apiJson with POST and provided body', async () => {
      const mockCreated = {
        id: 'tpl-new',
        owner_user_id: 1,
        name: 'New Template',
        description: '',
        primary_category: null,
        origin: 'authored',
        source_template_id: null,
        source_version_id: null,
        current_version_id: 'ver-1',
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '',
        input_schema: [],
        archived_at: null,
        created_at: '2026-10-08T00:00:00Z',
        updated_at: null,
      }
      apiJson.mockResolvedValueOnce(mockCreated)

      const body = { name: 'New Template', front_html: '{{Front}}' }
      const result = await createLibraryTemplate(body)
      expect(result).toBe(mockCreated)
      expect(apiJson).toHaveBeenCalledWith('/api/card-templates', 'POST', body)
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Validation failed'))
      await expect(createLibraryTemplate({ name: '' })).rejects.toThrow('Validation failed')
    })
  })

  describe('updateLibraryTemplate', () => {
    it('calls apiJson with PATCH, encoded template ID, and body', async () => {
      const mockUpdated = {
        id: 'tpl/1',
        owner_user_id: 1,
        name: 'Updated',
        description: '',
        primary_category: null,
        origin: 'authored',
        source_template_id: null,
        source_version_id: null,
        current_version_id: 'ver-2',
        front_html: '{{Front}}',
        back_html: '{{Back}}',
        shared_css: '',
        input_schema: [],
        archived_at: null,
        created_at: null,
        updated_at: '2026-10-08T00:00:00Z',
        affected_applications: ['app-1'],
      }
      apiJson.mockResolvedValueOnce(mockUpdated)

      const body = { name: 'Updated', change_note: 'bump' }
      const result = await updateLibraryTemplate('tpl/1', body)
      expect(result).toBe(mockUpdated)
      expect(apiJson).toHaveBeenCalledWith('/api/card-templates/tpl%2F1', 'PATCH', body)
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Version conflict'))
      await expect(updateLibraryTemplate('tpl-1', {})).rejects.toThrow('Version conflict')
    })
  })

  describe('previewLibraryTemplate', () => {
    it('calls apiRequest with POST, encoded ID, headers, stringified body, and forwards signal', async () => {
      const mockPreview = {
        front_html: '<div>Front</div>',
        back_html: '<div>Back</div>',
        front_renderer_payload: {},
        back_renderer_payload: {},
      }
      apiRequest.mockResolvedValueOnce(mockPreview)

      const controller = new AbortController()
      const body = { front_html: '{{Expression}}', sample_values: { Expression: 'test' } }
      const result = await previewLibraryTemplate('tpl/1', body, controller.signal)

      expect(result).toBe(mockPreview)
      expect(apiRequest).toHaveBeenCalledWith('/api/card-templates/tpl%2F1/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Compilation error'))
      await expect(previewLibraryTemplate('tpl-1', {})).rejects.toThrow('Compilation error')
    })
  })

  describe('archiveLibraryTemplate', () => {
    it('calls apiJson with PATCH, encoded ID, and archived payload', async () => {
      const mockArchived = { id: 'tpl/1', archived_at: '2026-10-08T00:00:00Z' }
      apiJson.mockResolvedValueOnce(mockArchived)

      const result = await archiveLibraryTemplate('tpl/1', true)
      expect(result).toBe(mockArchived)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl%2F1/archive',
        'PATCH',
        { archived: true },
      )

      apiJson.mockResolvedValueOnce({ id: 'tpl/1', archived_at: null })
      await archiveLibraryTemplate('tpl/1', false)
      expect(apiJson).toHaveBeenLastCalledWith(
        '/api/card-templates/tpl%2F1/archive',
        'PATCH',
        { archived: false },
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Archive failed'))
      await expect(archiveLibraryTemplate('tpl-1', true)).rejects.toThrow('Archive failed')
    })
  })

  describe('duplicateLibraryTemplate', () => {
    it('calls apiJson with POST, encoded ID, and provided body', async () => {
      const mockDuplicate = { id: 'tpl-copy', name: 'Copy of Tpl' }
      apiJson.mockResolvedValueOnce(mockDuplicate)

      const result = await duplicateLibraryTemplate('tpl/1', { name: 'Copy of Tpl' })
      expect(result).toBe(mockDuplicate)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl%2F1/duplicate',
        'POST',
        { name: 'Copy of Tpl' },
      )
    })

    it('calls apiJson with empty object body when body is omitted', async () => {
      apiJson.mockResolvedValueOnce({ id: 'tpl-copy' })

      await duplicateLibraryTemplate('tpl-1')
      expect(apiJson).toHaveBeenCalledWith(
        '/api/card-templates/tpl-1/duplicate',
        'POST',
        {},
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Duplicate forbidden'))
      await expect(duplicateLibraryTemplate('tpl-1')).rejects.toThrow('Duplicate forbidden')
    })
  })

  describe('fetchTemplateApplications', () => {
    it('calls apiRequest with encoded noteTypeId without include_retired when false or omitted', async () => {
      const mockResponse = {
        schema_version: 'template-applications.v2',
        items: [],
      }
      apiRequest.mockResolvedValueOnce(mockResponse)

      const result1 = await fetchTemplateApplications('nt/1')
      expect(result1).toBe(mockResponse)
      expect(apiRequest).toHaveBeenCalledWith('/api/note-types/nt%2F1/template-applications', {
        signal: undefined,
      })

      apiRequest.mockResolvedValueOnce(mockResponse)
      await fetchTemplateApplications('nt/1', false)
      expect(apiRequest).toHaveBeenLastCalledWith(
        '/api/note-types/nt%2F1/template-applications',
        { signal: undefined },
      )
    })

    it('appends ?include_retired=true ONLY when includeRetired is true', async () => {
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-applications.v2', items: [] })

      await fetchTemplateApplications('nt/1', true)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/template-applications?include_retired=true',
        { signal: undefined },
      )
    })

    it('forwards AbortSignal when provided', async () => {
      const controller = new AbortController()
      apiRequest.mockResolvedValueOnce({ schema_version: 'template-applications.v2', items: [] })

      await fetchTemplateApplications('nt-1', true, controller.signal)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/note-types/nt-1/template-applications?include_retired=true',
        { signal: controller.signal },
      )
    })

    it('propagates error when apiRequest rejects', async () => {
      apiRequest.mockRejectedValueOnce(new Error('Note type not found'))
      await expect(fetchTemplateApplications('nt-404')).rejects.toThrow('Note type not found')
    })
  })

  describe('attachLibraryTemplate', () => {
    it('calls apiJson with POST, encoded noteTypeId, and body', async () => {
      const mockApplication = {
        id: 'app-1',
        application_id: 'app-1',
        note_type_id: 'nt/1',
        template_id: 'tpl-1',
        occurrence_key: 'default',
        status_code: 'ACTIVE',
        display_name: null,
        position: 0,
        is_default: true,
        input_bindings: {},
        input_schema: [],
        warnings: [],
      }
      apiJson.mockResolvedValueOnce(mockApplication)

      const body = { template_id: 'tpl-1', occurrence_key: 'default' }
      const result = await attachLibraryTemplate('nt/1', body)
      expect(result).toBe(mockApplication)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/template-applications',
        'POST',
        body,
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Already attached'))
      await expect(attachLibraryTemplate('nt-1', { template_id: 'tpl-1' })).rejects.toThrow(
        'Already attached',
      )
    })
  })

  describe('updateTemplateApplication', () => {
    it('calls apiJson with PATCH, encoded noteTypeId and applicationId, and body', async () => {
      const mockUpdated = {
        id: 'app/1',
        application_id: 'app/1',
        note_type_id: 'nt/1',
        template_id: 'tpl-1',
        occurrence_key: 'default',
        status_code: 'ACTIVE',
        display_name: 'Renamed',
        position: 1,
        is_default: false,
        input_bindings: { Front: 'Word' },
        input_schema: [],
        warnings: [],
      }
      apiJson.mockResolvedValueOnce(mockUpdated)

      const patch = { display_name: 'Renamed', position: 1 }
      const result = await updateTemplateApplication('nt/1', 'app/1', patch)
      expect(result).toBe(mockUpdated)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/template-applications/app%2F1',
        'PATCH',
        patch,
      )
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Application not found'))
      await expect(updateTemplateApplication('nt-1', 'app-404', {})).rejects.toThrow(
        'Application not found',
      )
    })
  })

  describe('retireTemplateApplication', () => {
    it('calls apiJson with DELETE and strictly 2 arguments (encoded URL and DELETE, no body)', async () => {
      const mockRetired = {
        id: 'app/1',
        application_id: 'app/1',
        note_type_id: 'nt/1',
        template_id: 'tpl-1',
        occurrence_key: 'default',
        status_code: 'RETIRED',
        display_name: null,
        position: 0,
        is_default: false,
        input_bindings: {},
        input_schema: [],
        warnings: [],
      }
      apiJson.mockResolvedValueOnce(mockRetired)

      const result = await retireTemplateApplication('nt/1', 'app/1')
      expect(result).toBe(mockRetired)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/note-types/nt%2F1/template-applications/app%2F1',
        'DELETE',
      )
      const callArgs = apiJson.mock.calls[0]
      expect(callArgs.length).toBe(2)
      expect(callArgs[2]).toBeUndefined()
    })

    it('propagates error when apiJson rejects', async () => {
      apiJson.mockRejectedValueOnce(new Error('Cannot retire last application'))
      await expect(retireTemplateApplication('nt-1', 'app-1')).rejects.toThrow(
        'Cannot retire last application',
      )
    })
  })

  describe('fetchStudyTemplateInputs', () => {
    it('calls apiRequest with properly encoded deckId and query parameters', async () => {
      const mockResult = { schema_version: 'study-scope-compositions.v2', compositions: [] }
      apiRequest.mockResolvedValueOnce(mockResult)

      const result = await fetchStudyTemplateInputs('deck/1')
      expect(result).toBe(mockResult)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/study/scopes/deck/deck%2F1/compositions?include_template_inputs=1&include_counts=1',
        { signal: undefined },
      )
    })
  })

  describe('fetchStudyTemplatePreset', () => {
    it('calls apiRequest with properly encoded deckId', async () => {
      const mockPreset = { selected_compositions: [], input_bindings: {}, ask_before_study: true, stale_compositions: [] }
      apiRequest.mockResolvedValueOnce(mockPreset)

      const result = await fetchStudyTemplatePreset(42)
      expect(result).toBe(mockPreset)
      expect(apiRequest).toHaveBeenCalledWith(
        '/api/decks/42/study-template-preset',
        { signal: undefined },
      )
    })
  })

  describe('saveStudyTemplatePreset', () => {
    it('calls apiJson with PUT, encoded deckId, and payload', async () => {
      const payload = { selected_compositions: ['comp-1'], input_bindings: {}, ask_before_study: false }
      const mockSaved = { ...payload, stale_compositions: [] }
      apiJson.mockResolvedValueOnce(mockSaved)

      const result = await saveStudyTemplatePreset('42', payload)
      expect(result).toBe(mockSaved)
      expect(apiJson).toHaveBeenCalledWith(
        '/api/decks/42/study-template-preset',
        'PUT',
        payload,
      )
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

    it('generates library query key tuple with defaults', () => {
      expect(cardTemplateQueryKeys.library()).toEqual([
        'card-template',
        'library',
        '',
        'all',
        '',
        false,
      ])
      expect(cardTemplateQueryKeys.library({})).toEqual([
        'card-template',
        'library',
        '',
        'all',
        '',
        false,
      ])
    })

    it('generates library query key tuple with custom params', () => {
      expect(
        cardTemplateQueryKeys.library({
          q: 'kanji',
          group: 'mine',
          category: 'vocab',
          include_archived: true,
        }),
      ).toEqual(['card-template', 'library', 'kanji', 'mine', 'vocab', true])
    })

    it('generates libraryDetail query key tuple', () => {
      expect(cardTemplateQueryKeys.libraryDetail('tpl-99')).toEqual([
        'card-template',
        'library-detail',
        'tpl-99',
      ])
    })

    it('generates applications query key tuple with default includeRetired false', () => {
      expect(cardTemplateQueryKeys.applications('nt-1')).toEqual([
        'card-template',
        'applications',
        'nt-1',
        false,
      ])
    })

    it('generates applications query key tuple with includeRetired true', () => {
      expect(cardTemplateQueryKeys.applications('nt-1', true)).toEqual([
        'card-template',
        'applications',
        'nt-1',
        true,
      ])
    })
  })
})

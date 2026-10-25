// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { archiveLibraryTemplate, cardTemplateQueryKeys, fetchLibraryTemplate, previewLibraryTemplate, updateLibraryTemplate, type TemplateLibraryDetail, type TemplateLibraryPreview, type TemplateUpdateResponse } from '@/entities/card-template'
import { useTemplateLibraryEditor } from './useTemplateLibraryEditor'
vi.mock('@/entities/card-template', async (original) => ({ ...await original<typeof import('@/entities/card-template')>(), fetchLibraryTemplate: vi.fn(), updateLibraryTemplate: vi.fn(), previewLibraryTemplate: vi.fn(), archiveLibraryTemplate: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const detail = (id = 't1', head = 'v1'): TemplateLibraryDetail => ({ id, owner_user_id: 1, name: 'Template', description: '', primary_category: null, origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: head, front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '', archived_at: null, created_at: null, updated_at: null, input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: true }, { key: 'Back', label: 'Back', type: 'text', required: false }], application_count: 0, note_type_count: 0, applications: [] })
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (error: unknown) => void; const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail }); return { promise, resolve, reject } }
async function flush(ms = 20) { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
describe('useTemplateLibraryEditor preserves versioned drafts and request identity', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let editor: ReturnType<typeof useTemplateLibraryEditor>
  let server: TemplateLibraryDetail
  function Probe({ id }: { id: string }) { editor = useTemplateLibraryEditor(id); return null }
  beforeEach(() => {
    vi.clearAllMocks(); server = detail()
    vi.mocked(fetchLibraryTemplate).mockImplementation(async (id) => id === server.id ? structuredClone(server) : detail(id, `${id}-head`))
    vi.mocked(previewLibraryTemplate).mockResolvedValue({ front_html: 'preview', back_html: 'back', front_renderer_payload: {}, back_renderer_payload: {} })
    vi.mocked(updateLibraryTemplate).mockImplementation(async (_id, body) => { server = { ...server, ...body, name: body.name ?? server.name, description: body.description ?? server.description, primary_category: body.primary_category ?? null, current_version_id: 'v2' }; return { ...server, affected_applications: [] } })
    vi.mocked(archiveLibraryTemplate).mockImplementation(async (_id, archived) => { server = { ...server, archived_at: archived ? '2026-10-08T00:00:00Z' : null }; return server })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })
  async function render(id = 't1') { await act(async () => root.render(<QueryClientProvider client={client}><Probe id={id} /></QueryClientProvider>)); await flush() }
  it('keeps dirty sources and baseline head on background refetch then PATCHes that head', async () => {
    await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); server = { ...server, front_html: 'remote', current_version_id: 'remote-head' }
    await act(async () => { await client.invalidateQueries({ queryKey: cardTemplateQueryKeys.libraryDetail('t1') }) }); await flush()
    expect(editor.draft?.front_html).toBe('dirty'); await act(async () => editor.save()); await flush()
    expect(updateLibraryTemplate).toHaveBeenCalledWith('t1', expect.objectContaining({ front_html: 'dirty', expected_current_version_id: 'v1' }))
    expect(editor.draft?.front_html).toBe('dirty'); expect(editor.dirty).toBe(false)
    await act(async () => { editor.updateDraft({ front_html: 'next' }) }); await act(async () => editor.save()); await flush()
    expect(updateLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ expected_current_version_id: 'v2' }))
  })
  it('refuses stale writes without changing the draft or retrying with a new head', async () => {
    vi.mocked(updateLibraryTemplate).mockRejectedValue(new ApiError('stale', 409, 'TEMPLATE_VERSION_STALE')); await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); await act(async () => editor.save()); await flush()
    expect(editor.draft?.front_html).toBe('dirty'); expect(editor.saveError).toBe('Giao diện thẻ đã thay đổi. Hãy tải lại trước khi lưu.'); expect(editor.canSave).toBe(false); expect(updateLibraryTemplate).toHaveBeenCalledTimes(1)
  })
  it('accepts required unbound inputs while blocking invalid schema draft saves', async () => {
    await render(); expect(editor.canSave).toBe(true)
    await act(async () => editor.updateDraft({ input_schema: [{ key: 'FrontSide', label: 'Bad', type: 'text', required: false }] })); expect(editor.canSave).toBe(false); await act(async () => editor.save()); expect(updateLibraryTemplate).not.toHaveBeenCalled()
  })
  it('ignores a late PATCH after route changes, even after returning to the same ID', async () => {
    const request = deferred<TemplateUpdateResponse>(); vi.mocked(updateLibraryTemplate).mockReturnValue(request.promise); await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); await act(async () => editor.save()); await render('t2'); await render('t1')
    await act(async () => request.resolve({ ...detail(), front_html: 'late response', current_version_id: 'late-head', affected_applications: [] })); await flush()
    expect(editor.draft?.front_html).toBe('{{Front}}')
  })
  it('explicitly replaces an unchanged-source restore and fetches its complete schema/head', async () => {
    await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); const request = deferred<TemplateLibraryDetail>(); vi.mocked(fetchLibraryTemplate).mockReturnValueOnce(request.promise)
    let restore!: Promise<void>
    await act(async () => { restore = editor.refreshAndReplaceDraft({ id: 't1', note_type_id: null, name: 'Template', front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '', current_version_id: 'v-restored', position: 0, is_default: false, updated_at: null }) })
    expect(editor.draft?.front_html).toBe('{{Front}}'); expect(editor.isReplacingDraft).toBe(true); expect(editor.canSave).toBe(false)
    server = { ...detail('t1', 'v-restored'), input_schema: [{ key: 'Restored', label: 'Restored', type: 'audio', required: false }] }
    await act(async () => { request.resolve(server); await restore }); await flush()
    expect(editor.draft?.input_schema).toEqual(server.input_schema); expect(editor.dirty).toBe(false); expect(editor.isReplacingDraft).toBe(false)
  })
  it('keeps the draft if a reload fails and allows explicit reload retry', async () => {
    await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); vi.mocked(fetchLibraryTemplate).mockRejectedValueOnce(new Error('network'))
    await act(async () => { await expect(editor.refreshAndReplaceDraft()).rejects.toThrow('network') }); expect(editor.draft?.front_html).toBe('dirty'); expect(editor.refreshError).toBe('network'); expect(editor.canSave).toBe(false)
    await act(async () => { await editor.refreshAndReplaceDraft() }); await flush(); expect(editor.draft?.front_html).toBe('{{Front}}'); expect(editor.refreshError).toBeNull()
  })
  it('explicitly replaces dirty sources and full schema after a source update with unchanged cached HTML', async () => {
    await render(); await act(async () => editor.updateDraft({ front_html: 'dirty draft' }))
    server.input_schema = [{ key: 'Audio', label: 'Received audio', type: 'audio', required: false }]
    server.current_version_id = 'v-from-source-update'
    await act(async () => { await editor.refreshAndReplaceDraft() }); await flush()
    expect(editor.draft?.front_html).toBe('{{Front}}'); expect(editor.draft?.input_schema).toEqual(server.input_schema); expect(editor.dirty).toBe(false)
    await act(async () => editor.updateDraft({ front_html: 'new draft' })); await act(async () => editor.save()); await flush()
    expect(updateLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ expected_current_version_id: 'v-from-source-update' }))
  })
  it('debounces preview, aborts obsolete calls, keeps empty samples and accepts only the latest response', async () => {
    const first = deferred<TemplateLibraryPreview>(); const second = deferred<TemplateLibraryPreview>(); vi.mocked(previewLibraryTemplate).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    await render(); expect(previewLibraryTemplate).not.toHaveBeenCalled(); await flush(510)
    const firstSignal = vi.mocked(previewLibraryTemplate).mock.calls[0][2]!
    await act(async () => { editor.setSampleValue('Front', ''); editor.updateDraft({ front_html: 'changed' }) }); expect(firstSignal.aborted).toBe(true)
    await flush(510); expect(previewLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ front_html: 'changed', sample_values: { Front: '', Back: 'Sample text' } }), expect.any(AbortSignal))
    await act(async () => second.resolve({ front_html: 'latest', back_html: '', front_renderer_payload: {}, back_renderer_payload: {} })); await act(async () => first.resolve({ front_html: 'old', back_html: '', front_renderer_payload: {}, back_renderer_payload: {} })); expect(editor.previewResult?.front_html).toBe('latest')
    await act(async () => editor.updateDraft({ input_schema: [] })); expect(editor.sampleValues).toEqual({})
    await act(async () => editor.updateDraft({ input_schema: detail().input_schema })); expect(editor.sampleValues).toEqual({})
  })
  it('archives with the explicit boolean without discarding draft content', async () => {
    await render(); await act(async () => editor.updateDraft({ front_html: 'dirty' })); await act(async () => { await editor.archive(true) }); await flush()
    expect(archiveLibraryTemplate).toHaveBeenCalledWith('t1', true); expect(editor.draft?.front_html).toBe('dirty'); expect(editor.template?.archived_at).not.toBeNull()
  })
  it('keeps legal prototype-named input samples empty until explicitly provided', async () => {
    server.input_schema = ['__proto__', 'constructor', 'toString'].map((key) => ({ key, label: key, type: 'text', required: false }))
    await render(); expect(Object.getPrototypeOf(editor.sampleValues)).toBeNull()
    for (const key of ['__proto__', 'constructor', 'toString']) expect(editor.sampleValues[key]).toBeUndefined()
    await act(async () => editor.setSampleValue('__proto__', 'safe sample')); expect(editor.sampleValues.__proto__).toBe('safe sample'); expect(editor.sampleValues.constructor).toBeUndefined()
    await flush(510); expect(previewLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ sample_values: JSON.parse('{"__proto__":"safe sample","constructor":"Sample text","toString":"Sample text"}') }), expect.any(AbortSignal))
  })

  it('sends native samples only to preview, resets on type changes, and never saves them', async () => {
    server.input_schema = [{ key: 'Items', label: 'Items', type: 'array', required: false }]
    await render(); await flush(510)
    expect(previewLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ sample_values: { Items: ['First item', 'Second item', 'Third item'] } }), expect.any(AbortSignal))
    await act(async () => editor.setSampleValue('Items', ['one', ['two', '']]))
    expect(editor.dirty).toBe(false)
    await flush(510)
    expect(previewLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ sample_values: { Items: ['one', ['two', '']] } }), expect.any(AbortSignal))
    await act(async () => editor.updateDraft({ front_html: '{{#Items}}{{.}}{{/Items}}' }))
    await act(async () => editor.save()); await flush()
    const body = vi.mocked(updateLibraryTemplate).mock.calls[0][1]
    expect(body).not.toHaveProperty('sample_values')
    expect(body).not.toHaveProperty('sampleValues')
    await act(async () => editor.updateDraft({ input_schema: [{ key: 'Items', label: 'Items', type: 'text', required: false }] }))
    expect(editor.sampleValues.Items).toBeUndefined()
    await flush(510)
    expect(previewLibraryTemplate).toHaveBeenLastCalledWith('t1', expect.objectContaining({ sample_values: { Items: 'Sample text' } }), expect.any(AbortSignal))
    await render('t2'); expect(editor.sampleValues).toEqual({})
  })
})

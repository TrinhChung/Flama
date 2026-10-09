// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import { archiveLibraryTemplate, fetchLibraryTemplate, fetchTemplateVersion, fetchTemplateVersions, previewLibraryTemplate, restoreTemplateVersion, updateLibraryTemplate, type TemplateLibraryDetail, type TemplateVersionDetail } from '@/entities/card-template'
import { TemplateDetailPage } from './TemplateDetailPage'
const preview = vi.hoisted(() => vi.fn())
const composition = vi.hoisted(() => ({ apply: vi.fn(), distribution: vi.fn() }))
vi.mock('@/entities/card-template', async (original) => ({ ...await original<typeof import('@/entities/card-template')>(), fetchLibraryTemplate: vi.fn(), updateLibraryTemplate: vi.fn(), previewLibraryTemplate: vi.fn(), archiveLibraryTemplate: vi.fn(), fetchTemplateVersions: vi.fn(), fetchTemplateVersion: vi.fn(), restoreTemplateVersion: vi.fn() }))
vi.mock('@/features/note-types/components/NoteTypeLivePreview', () => ({ NoteTypeLivePreview: preview }))
vi.mock('@/features/template-distribution', () => ({ TemplateDistributionPanel: composition.distribution }))
vi.mock('../components/ApplyTemplateWizard', () => ({ ApplyTemplateWizard: composition.apply }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
const fixture = (id = 't1'): TemplateLibraryDetail => ({ id, owner_user_id: 1, name: 'Reusable template', description: 'Description', primary_category: null, origin: 'authored', source_template_id: null, source_version_id: null, current_version_id: 'v2', front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '', archived_at: null, created_at: null, updated_at: null, input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: true }], application_count: 1, note_type_count: 1, applications: [{ id: 'a1', application_id: 'a1', note_type_id: 'nt1', note_type_name: 'Vocabulary', occurrence_key: 'second', display_name: 'Reading', position: 0, is_default: true }] })
const version: TemplateVersionDetail = { id: 'v1', template_id: 't1', version_no: 1, content_hash: 'hash', change_note: '', origin: 'create', created_at: '2026-10-08T00:00:00Z', created_by: null, is_current: false, front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '', input_schema: [] }
const findButton = (label: string) => [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === label)!
async function flush(ms = 20) { await act(async () => { await new Promise((resolve) => setTimeout(resolve, ms)) }) }
async function text(element: HTMLInputElement | HTMLTextAreaElement, value: string) { await act(async () => { Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!.call(element, value); element.dispatchEvent(new Event('input', { bubbles: true })) }) }
describe('TemplateDetailPage composes editor, sandbox preview, history and usages', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  let server: TemplateLibraryDetail
  let navigate: ReturnType<typeof useNavigate>
  function Navigation() { navigate = useNavigate(); return null }
  beforeEach(() => {
    vi.clearAllMocks(); server = fixture(); preview.mockReturnValue(null); composition.apply.mockReturnValue(null); composition.distribution.mockReturnValue(null)
    vi.mocked(fetchLibraryTemplate).mockImplementation(async (id) => id === 't1' ? structuredClone(server) : { ...fixture(id), front_html: 'second template' })
    vi.mocked(updateLibraryTemplate).mockImplementation(async (_id, body) => { server = { ...server, ...body, primary_category: body.primary_category ?? null, current_version_id: 'v3' }; return { ...server, affected_applications: ['a1'] } })
    vi.mocked(previewLibraryTemplate).mockResolvedValue({ front_html: 'sanitized front', back_html: 'sanitized back', front_renderer_payload: { source: 'front' }, back_renderer_payload: { source: 'back' } })
    vi.mocked(archiveLibraryTemplate).mockImplementation(async (_id, archived) => { server.archived_at = archived ? '2026-10-08T00:00:00Z' : null; return { ...server } })
    vi.mocked(fetchTemplateVersions).mockResolvedValue({ schema_version: 'template-versions.v2', template_id: 't1', current_version_id: 'v2', items: [version] }); vi.mocked(fetchTemplateVersion).mockResolvedValue(version)
    vi.mocked(restoreTemplateVersion).mockImplementation(async () => { server = { ...server, current_version_id: 'v3', input_schema: [{ key: 'Audio', label: 'Restored audio', type: 'audio', required: false }] }; return { id: 't1', note_type_id: null, name: server.name, front_html: server.front_html, back_html: server.back_html, shared_css: server.shared_css, current_version_id: 'v3', position: 0, is_default: false, updated_at: null } })
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render() { await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/card-templates/t1']}><Navigation /><Routes><Route path="/card-templates/:id" element={<TemplateDetailPage />} /></Routes></MemoryRouter></QueryClientProvider>)); await flush() }
  async function restore() { await act(async () => findButton('Lịch sử').click()); await flush(); await act(async () => [...document.querySelectorAll('button')].find((el) => el.getAttribute('aria-pressed') !== null)!.click()); await flush(); await act(async () => findButton('Khôi phục phiên bản này').click()); await act(async () => findButton('Khôi phục').click()); await flush() }
  it('shows active usage without sync actions and saves source/schema with the baseline head', async () => {
    await render(); expect(container.querySelector('a[href="/flashcards/note-types/nt1"]')?.textContent).toBe('Vocabulary'); expect(container.textContent).toContain('Reading · second'); expect(container.textContent).not.toContain('Đồng bộ')
    await text(container.querySelector('textarea')!, '<b>draft</b>'); await act(async () => findButton('Lưu thay đổi').click()); await flush()
    expect(updateLibraryTemplate).toHaveBeenCalledWith('t1', expect.objectContaining({ front_html: '<b>draft</b>', input_schema: fixture().input_schema, expected_current_version_id: 'v2' }))
  })
  it('passes backend renderer payloads and matching raw preview field IDs to the sandbox', async () => {
    await render(); await flush(510)
    expect(preview).toHaveBeenLastCalledWith(expect.objectContaining({ cardId: 'library-preview:t1', frontPayload: { source: 'front' }, backPayload: { source: 'back' }, frontHtml: 'sanitized front', fieldDefs: [{ id: 'f_0', name: 'Front', field_type: 'text', position: 0 }] }), undefined)
    expect(container.innerHTML).not.toContain('sanitized front')
  })
  it('archives only after confirmation and can unarchive', async () => {
    await render(); await act(async () => findButton('Lưu trữ').click()); expect(archiveLibraryTemplate).not.toHaveBeenCalled()
    const confirm = [...document.querySelectorAll('button')].filter((el) => el.textContent?.trim() === 'Lưu trữ').at(-1)!
    await act(async () => confirm.click()); await flush(); expect(archiveLibraryTemplate).toHaveBeenCalledWith('t1', true)
    await act(async () => findButton('Bỏ lưu trữ').click()); await flush(); expect(archiveLibraryTemplate).toHaveBeenLastCalledWith('t1', false)
  })
  it('restores sources equal to cached server sources and refetches the full input schema', async () => {
    await render(); await text(container.querySelector('textarea')!, 'dirty'); await restore(); expect(container.querySelector('textarea')?.value).toBe('{{Front}}'); expect(document.body.textContent).toContain('Restored audio'); expect(vi.mocked(fetchLibraryTemplate).mock.calls.length).toBeGreaterThanOrEqual(2)
  })
  it('keeps dirty sources on restore errors', async () => {
    vi.mocked(restoreTemplateVersion).mockRejectedValue(new Error('restore failed')); await render(); await text(container.querySelector('textarea')!, 'dirty'); await restore(); expect(container.querySelector('textarea')?.value).toBe('dirty')
  })
  it('requires confirmation before replacing a stale dirty draft', async () => {
    vi.mocked(updateLibraryTemplate).mockRejectedValue(new ApiError('stale', 409, 'TEMPLATE_VERSION_STALE')); await render(); await text(container.querySelector('textarea')!, 'dirty'); await act(async () => findButton('Lưu thay đổi').click()); await flush()
    expect(container.textContent).toContain('Mẫu thẻ đã thay đổi. Hãy tải lại trước khi lưu.'); await act(async () => findButton('Tải lại').click()); expect(container.querySelector('textarea')?.value).toBe('dirty')
    await act(async () => findButton('Hủy').click()); expect(container.querySelector('textarea')?.value).toBe('dirty'); expect(updateLibraryTemplate).toHaveBeenCalledTimes(1)
  })
  it('resets draft, selection and dialogs when the route changes', async () => {
    await render(); await text(container.querySelector('textarea')!, 'dirty'); await act(async () => findButton('Lịch sử').click()); await flush(); await act(async () => navigate('/card-templates/t2')); await flush()
    expect(container.querySelector('textarea')?.value).toBe('second template'); expect(document.body.textContent).not.toContain('Lịch sử phiên bản')
  })
  it('opens the apply wizard with the saved template instead of unsaved editor sources', async () => {
    await render(); await text(container.querySelector('textarea')!, 'unsaved front'); await text(container.querySelector<HTMLInputElement>('#library-template-name')!, 'Unsaved name')
    await act(async () => findButton('Áp dụng vào loại thẻ').click())
    expect(composition.apply).toHaveBeenLastCalledWith(expect.objectContaining({ open: true, template: expect.objectContaining({ id: 't1', name: 'Reusable template', front_html: '{{Front}}' }) }), undefined)
  })
  it('disables new applications while the template is archived', async () => {
    server.archived_at = '2026-10-08T00:00:00Z'; await render(); expect(findButton('Áp dụng vào loại thẻ').disabled).toBe(true)
    await act(async () => findButton('Áp dụng vào loại thẻ').click()); expect(composition.apply).toHaveBeenLastCalledWith(expect.objectContaining({ open: false }), undefined)
  })
  it('explicitly replaces dirty sources and schema after a distribution mutation, even with unchanged cached HTML', async () => {
    await render(); await text(container.querySelector('textarea')!, 'dirty draft')
    const props = composition.distribution.mock.calls.at(-1)![0] as { templateId: string; onSourceChanged: () => Promise<void> }
    expect(props.templateId).toBe('t1')
    server.input_schema = [{ key: 'Audio', label: 'Received audio', type: 'audio', required: false }]
    server.current_version_id = 'v-from-distribution'
    await act(async () => { await props.onSourceChanged() }); await flush()
    expect(container.querySelector('textarea')?.value).toBe('{{Front}}'); expect(container.textContent).toContain('Received audio')
    expect(composition.distribution).toHaveBeenLastCalledWith(expect.objectContaining({ currentVersionId: 'v-from-distribution' }), undefined)
  })
  it('locks the editor and save through both restore POST and full schema refetch', async () => {
    await render(); await text(container.querySelector('textarea')!, 'dirty')
    let resolvePost!: (value: Awaited<ReturnType<typeof restoreTemplateVersion>>) => void
    vi.mocked(restoreTemplateVersion).mockImplementation(() => new Promise((done) => { resolvePost = done }))
    await restore(); expect(container.querySelector('textarea')?.readOnly).toBe(true); expect(findButton('Lưu thay đổi').disabled).toBe(true)
    let resolveGet!: (value: TemplateLibraryDetail) => void
    vi.mocked(fetchLibraryTemplate).mockReturnValueOnce(new Promise((done) => { resolveGet = done }))
    await act(async () => resolvePost({ id: 't1', note_type_id: null, name: server.name, front_html: '{{Front}}', back_html: '{{Back}}', shared_css: '', current_version_id: 'v3', position: 0, is_default: false, updated_at: null })); await flush()
    expect(container.querySelector('textarea')?.readOnly).toBe(true); expect(findButton('Lưu thay đổi').disabled).toBe(true)
    server.current_version_id = 'v3'
    await act(async () => resolveGet(server)); await flush()
    expect(container.querySelector('textarea')?.readOnly).toBe(false); expect(findButton('Lưu thay đổi').disabled).toBe(false)
  })
  it('renders legal prototype-named sample keys as empty inputs', async () => {
    server.input_schema = ['__proto__', 'constructor'].map((key) => ({ key, label: key, type: 'text', required: false }))
    await render(); expect(container.querySelector<HTMLInputElement>('#sample-__proto__')?.value).toBe(''); expect(container.querySelector<HTMLInputElement>('#sample-constructor')?.value).toBe('')
  })
})

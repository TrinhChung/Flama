// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createLibraryTemplate, type TemplateLibraryTemplate } from '@/entities/card-template'
import { CreateTemplateDialog } from './CreateTemplateDialog'
vi.mock('@/entities/card-template', async (original) => ({ ...await original<typeof import('@/entities/card-template')>(), createLibraryTemplate: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
function Fixture() { const [open, setOpen] = useState(true); const location = useLocation(); return <><output>{location.pathname}</output><button onClick={() => setOpen(true)}>Reopen</button><CreateTemplateDialog open={open} onOpenChange={setOpen} /></> }
async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 15)) }) }
function button(label: string) { return [...document.querySelectorAll('button')].find((el) => el.textContent?.trim() === label)! }
async function name(value: string) { await act(async () => { const input = document.querySelector<HTMLInputElement>('#create-template-name')!; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, value); input.dispatchEvent(new Event('input', { bubbles: true })) }) }
describe('CreateTemplateDialog', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  beforeEach(() => { vi.clearAllMocks(); client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } }); container = document.createElement('div'); document.body.append(container); root = createRoot(container) })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove(); document.body.innerHTML = '' })
  async function render() { await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><Fixture /></MemoryRouter></QueryClientProvider>)); await flush() }
  it('blocks whitespace and submits the default schema then navigates to encoded ID', async () => {
    vi.mocked(createLibraryTemplate).mockResolvedValue({ id: 'new/id' } as TemplateLibraryTemplate); await render(); await name('   '); expect(button('Tạo mẫu').disabled).toBe(true)
    await name('  New template  '); await act(async () => button('Tạo mẫu').click()); await flush()
    expect(createLibraryTemplate).toHaveBeenCalledWith({ name: 'New template', description: '', front_html: '{{Front}}', back_html: '{{Front}}<hr>{{Back}}', shared_css: '', input_schema: [{ key: 'Front', label: 'Front', type: 'text', required: false }, { key: 'Back', label: 'Back', type: 'text', required: false }] })
    expect(container.querySelector('output')?.textContent).toBe('/card-templates/new%2Fid')
  })
  it('keeps input and server error for retry', async () => { vi.mocked(createLibraryTemplate).mockRejectedValue(new Error('bad name')); await render(); await name('Draft'); await act(async () => button('Tạo mẫu').click()); await flush(); expect(document.querySelector<HTMLInputElement>('#create-template-name')?.value).toBe('Draft'); expect(document.body.textContent).toContain('bad name') })
  it('ignores a late create response after close and reopen', async () => {
    let resolve!: (value: TemplateLibraryTemplate) => void
    vi.mocked(createLibraryTemplate).mockImplementation(() => new Promise((done) => { resolve = done })); await render(); await name('Draft'); await act(async () => button('Tạo mẫu').click()); await act(async () => button('Hủy').click()); await act(async () => button('Reopen').click())
    await act(async () => resolve({ id: 'old-result' } as TemplateLibraryTemplate)); await flush(); expect(container.querySelector('output')?.textContent).toBe('/'); expect(document.querySelector<HTMLInputElement>('#create-template-name')?.value).toBe('')
  })
})

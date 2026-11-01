// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { FieldEditorPreview } from './FieldEditorPreview'

const state = vi.hoisted(() => ({ renderFrame: vi.fn().mockReturnValue(null), preview: vi.fn(), createUrl: vi.fn(), revokeUrl: vi.fn() }))
vi.mock('@/entities/flashcard', async (original) => ({ ...await original<typeof import('@/entities/flashcard')>(), CardRendererFrame: state.renderFrame }))
vi.mock('@/shared/api/client', async (original) => ({ ...await original<typeof import('@/shared/api/client')>(), apiJson: state.preview }))

function Harness({ fieldType }: { fieldType: string }) {
  const [value, setValue] = useState('')
  const [file, setFile] = useState<File | null>(null)
  return <FieldEditorPreview fieldType={fieldType} value={value} onChange={setValue} localFile={file} onFileChange={setFile} />
}

describe('field input demos', () => {
  let root: Root
  let container: HTMLDivElement
  let queryClient: QueryClient
  const flush = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 300)) })
  const button = (text: string) => Array.from(container.querySelectorAll('button')).find((item) => item.textContent?.trim() === text)!
  const render = async (fieldType: string) => {
    await act(async () => root.render(<QueryClientProvider client={queryClient}><Harness key={fieldType} fieldType={fieldType} /></QueryClientProvider>))
  }
  beforeEach(async () => {
    await i18n.changeLanguage('vi')
    state.preview.mockReset(); state.renderFrame.mockClear()
    state.createUrl.mockReset().mockImplementation((file: File) => `blob:preview/${file.name}`)
    state.revokeUrl.mockClear()
    const NativeURL = URL
    vi.stubGlobal('URL', class extends NativeURL { static createObjectURL = state.createUrl; static revokeObjectURL = state.revokeUrl })
    state.preview.mockResolvedValue({ front_html: '<p>Safe result</p>', front_renderer_payload: { html: '<p>Safe result</p>', allowed_media_urls: [], allowed_audio_urls: [] } })
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
  })
  afterEach(async () => { await act(async () => root.unmount()); queryClient.clear(); container.remove(); vi.unstubAllGlobals() })

  it.each(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram'])('shows an appropriate editable demo and empty state for %s', async (fieldType) => {
    await render(fieldType)
    const editor = container.querySelector('#field-editor-sample') as HTMLInputElement | HTMLTextAreaElement
    expect(editor.tagName).toBe(fieldType === 'text' ? 'INPUT' : 'TEXTAREA')
    expect(editor.value).toBe('')
    expect(container.textContent).toContain('không lưu vào note')
    await act(async () => button('Dùng mẫu').click())
    expect(editor.value.length).toBeGreaterThan(0)
    if (fieldType === 'audio') expect(container.querySelector('audio')?.getAttribute('src')).toContain('/store/sample-audio.mp3')
    if (fieldType === 'image' || fieldType === 'diagram') expect(container.querySelector('img')?.getAttribute('src')).toContain(`/store/sample-${fieldType}`)
    expect(state.preview).not.toHaveBeenCalled()
    await act(async () => button('Xóa mẫu').click())
    expect(editor.value).toBe('')
    expect(container.querySelector('img, audio')).toBeNull()
  })

  it.each(['richtext', 'markdown'])('renders %s samples through the backend and existing sandbox', async (fieldType) => {
    await render(fieldType)
    await act(async () => button('Dùng mẫu').click())
    await flush()
    const sample = (container.querySelector('#field-editor-sample') as HTMLTextAreaElement).value
    await act(async () => button('Xem kết quả').focus())
    await flush()
    expect(state.preview).toHaveBeenCalledWith('/api/note-types/preview', 'POST', {
      front_html: '{{{Sample}}}', back_html: '{{{Sample}}}', shared_css: '',
      fields: [{ name: 'Sample', field_type: fieldType }], field_values: { Sample: sample },
    })
    expect(state.renderFrame.mock.calls.at(-1)?.[0].frontPayload.html).toBe('<p>Safe result</p>')
    expect(container.querySelector('p')?.innerHTML).not.toContain('<strong>')
  })

  it('rejects executable media URLs without staging or uploading media', async () => {
    await render('image')
    const editor = container.querySelector('#field-editor-sample') as HTMLTextAreaElement
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(editor, 'javascript:alert(1)')
      editor.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('Tham chiếu media này chưa hợp lệ')
    expect(state.preview).not.toHaveBeenCalled()
  })

  it.each([['image', 'image/png', 'img'], ['audio', 'audio/mpeg', 'audio']])('chooses and replaces local %s samples, revoking object URLs', async (fieldType, mime, tag) => {
    await render(fieldType)
    const input = container.querySelector('input[type="file"]') as HTMLInputElement
    const chooseFile = async (name: string) => act(async () => {
      Object.defineProperty(input, 'files', { configurable: true, value: [new File(['sample'], name, { type: mime })] })
      input.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await chooseFile('first')
    expect(container.querySelector(tag)?.getAttribute('src')).toBe('blob:preview/first')
    expect(button('Thay tệp mẫu')).toBeDefined()
    await chooseFile('second')
    expect(state.revokeUrl).toHaveBeenCalledWith('blob:preview/first')
    expect(container.querySelector(tag)?.getAttribute('src')).toBe('blob:preview/second')
    await act(async () => button('Xóa mẫu').click())
    expect(state.revokeUrl).toHaveBeenCalledWith('blob:preview/second')
    expect(container.querySelector(tag)).toBeNull()
    expect(state.preview).not.toHaveBeenCalled()
  })

  it('inserts supported HTML formatting into the richtext sample source', async () => {
    await render('richtext')
    const insertBold = container.querySelector('button[aria-label="Chèn chữ đậm"]') as HTMLButtonElement
    await act(async () => insertBold.click())
    expect((container.querySelector('#field-editor-sample') as HTMLTextAreaElement).value).toBe('<strong>nội dung</strong>')
    expect(container.querySelector('strong')).toBeNull()
    expect(state.preview).not.toHaveBeenCalled()
  })
})

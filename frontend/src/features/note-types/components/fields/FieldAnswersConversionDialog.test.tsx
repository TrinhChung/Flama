// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/client'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'
import { FieldAnswersConversionDialog } from './FieldAnswersConversionDialog'
import { FieldAnswersRestoreDialog } from './FieldAnswersRestoreDialog'

const api = vi.hoisted(() => ({ get: vi.fn(), mutate: vi.fn() }))
vi.mock('@/app/api', () => ({ appApi: api }))

const field: FieldDefItem = { id: 'f-1', name: 'Meaning', field_type: 'text', required: false, position: 1, identity_role: null }
const source = {
  schema_version: 'field-answers-conversion.v1',
  field,
  convertible: true,
  blocked_reason: null,
  notes: [
    { note_id: 'n-1', value: 'ăn, dùng bữa' },
    { note_id: 'n-2', value: '<b>uống</b>' },
    { note_id: 'n-3', value: '' },
  ],
}

async function flush() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)) }) }
const button = (label: string) => [...document.querySelectorAll('button')].find((el) => el.textContent?.includes(label))!

describe('answers conversion dialogs', () => {
  let root: Root
  let container: HTMLDivElement
  let client: QueryClient
  const done = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue(source)
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    URL.createObjectURL = vi.fn(() => 'blob:backup')
    URL.revokeObjectURL = vi.fn()
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear()
    container.remove()
    document.body.innerHTML = ''
  })

  async function renderConversion() {
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <FieldAnswersConversionDialog open onOpenChange={() => {}} noteTypeId="nt-1" field={field} onConverted={done} />
      </QueryClientProvider>,
    ))
    await flush()
  }

  it('previews the split, requires a backup and applies every Note at once', async () => {
    api.mutate.mockResolvedValue({ schema_version: 'field-answers-conversion.v1', field: { ...field, field_type: 'answers' }, note_count: 3, changed_note_count: 2 })
    await renderConversion()
    expect(api.get).toHaveBeenCalledWith('/note-types/nt-1/fields/f-1/answers-conversion')
    expect(document.body.textContent).toContain('3 Note · 1 cần xem · 1 không đổi')
    expect(document.body.textContent).toContain('Có HTML, sẽ bỏ định dạng')
    const apply = button('Áp dụng cho 3 Note')
    expect(apply.disabled).toBe(true)
    await act(async () => button('Tải bản sao lưu').click())
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
    expect(button('Áp dụng cho 3 Note').disabled).toBe(false)
    await act(async () => button('Áp dụng cho 3 Note').click())
    await flush()
    expect(api.mutate).toHaveBeenCalledWith('/note-types/nt-1/fields/f-1/answers-conversion', 'POST', {
      target_type: 'answers',
      expected_field_type: 'text',
      notes: [
        { note_id: 'n-1', expected: 'ăn, dùng bữa', value: 'ăn\ndùng bữa' },
        { note_id: 'n-2', expected: '<b>uống</b>', value: 'uống' },
        { note_id: 'n-3', expected: '', value: '' },
      ],
    })
    expect(done).toHaveBeenCalledTimes(1)
  })

  it('offers a reload when Notes changed since the preview', async () => {
    api.mutate.mockRejectedValue(new ApiError('Notes changed since the preview.', 409, 'NOTES_CHANGED'))
    await renderConversion()
    await act(async () => button('Tải bản sao lưu').click())
    await act(async () => button('Áp dụng cho 3 Note').click())
    await flush()
    expect(document.body.textContent).toContain('Notes changed since the preview.')
    await act(async () => button('Tải lại xem trước').click())
    await flush()
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(done).not.toHaveBeenCalled()
  })

  it('explains why a field cannot be converted', async () => {
    api.get.mockResolvedValue({ ...source, convertible: false, blocked_reason: 'PRIMARY_FIELD', notes: [] })
    await renderConversion()
    expect(document.body.textContent).toContain('Trường định danh chính phải giữ kiểu Văn bản.')
    expect(button('Tải bản sao lưu').disabled).toBe(true)
  })

  it('restores from a backup file and keeps newer Notes', async () => {
    const answersField = { ...field, field_type: 'answers' }
    api.get.mockResolvedValue({ ...source, field: answersField, notes: [{ note_id: 'n-1', value: 'ăn\ndùng bữa' }, { note_id: 'n-9', value: 'mới' }] })
    api.mutate.mockResolvedValue({ schema_version: 'field-answers-conversion.v1', field, note_count: 2, changed_note_count: 1 })
    await act(async () => root.render(
      <QueryClientProvider client={client}>
        <FieldAnswersRestoreDialog open onOpenChange={() => {}} noteTypeId="nt-1" field={answersField} onRestored={done} />
      </QueryClientProvider>,
    ))
    await flush()
    const backup = {
      schema_version: 'flama-answers-backup.v1', note_type_id: 'nt-1', field_id: 'f-1', field_name: 'Meaning',
      original_type: 'text', created_at: '2026-10-10T00:00:00.000Z',
      notes: [{ note_id: 'n-1', value: 'ăn, dùng bữa' }, { note_id: 'n-gone', value: 'x' }],
    }
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
    const file = new File([JSON.stringify(backup)], 'backup.json', { type: 'application/json' })
    Object.defineProperty(input, 'files', { value: [file] })
    await act(async () => { input.dispatchEvent(new Event('change', { bubbles: true })) })
    await flush()
    expect(document.body.textContent).toContain('Khôi phục 1 Note về kiểu Văn bản · giữ nguyên 1 Note mới · 1 Note trong bản sao lưu không còn')
    await act(async () => button('Khôi phục').click())
    await flush()
    expect(api.mutate).toHaveBeenCalledWith('/note-types/nt-1/fields/f-1/answers-conversion', 'POST', {
      target_type: 'text',
      expected_field_type: 'answers',
      notes: [
        { note_id: 'n-1', expected: 'ăn\ndùng bữa', value: 'ăn, dùng bữa' },
        { note_id: 'n-9', expected: 'mới', value: 'mới' },
      ],
    })
    expect(done).toHaveBeenCalledTimes(1)
  })
})

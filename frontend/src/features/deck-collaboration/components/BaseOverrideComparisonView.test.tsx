// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import '@/shared/config/i18n'
import { ApiError } from '@/shared/api/client'
import { BaseOverrideComparisonView } from './BaseOverrideComparisonView'
import type { BaseOverrideComparisonPage } from '../model/baseComparisonTypes'

const { getComparison, resetOverride, keepOverride, toastError } = vi.hoisted(() => ({
  getComparison: vi.fn(), resetOverride: vi.fn(), keepOverride: vi.fn(), toastError: vi.fn(),
}))
vi.mock('../api/baseComparisonApi', () => ({
  getBaseOverrideComparison: getComparison, resetBaseOverride: resetOverride, keepBaseOverride: keepOverride,
}))
vi.mock('sonner', () => ({ toast: { error: toastError } }))
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function page(overrides: Partial<BaseOverrideComparisonPage> = {}): BaseOverrideComparisonPage {
  return {
    content_model: 'published_base', install_id: 'install-1', deck_title: 'N1',
    overlay_revision: 21, content_revision: 7, next_cursor: null,
    items: [{ id: 'override-1', note_id: 'note-1', field_identity: 'field-1',
      field_name: 'Meaning', operation: 'set', personal_value: ['mine', ['nested']],
      base_value: ['new base'], base_exists: true, base_changed: true, current_base_hash: 'base-hash',
      note_deleted: false, field_deleted: false }], ...overrides,
  }
}

describe('Published Base personal comparison', () => {
  let host: HTMLDivElement
  let root: Root
  let client: QueryClient
  beforeEach(() => {
    getComparison.mockReset(); resetOverride.mockReset(); keepOverride.mockReset(); toastError.mockReset()
    host = document.createElement('div'); document.body.append(host)
    root = createRoot(host)
    client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } })
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    client.clear(); host.remove()
  })
  async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) }) }
  async function render() {
    await act(async () => root.render(<QueryClientProvider client={client}><MemoryRouter><BaseOverrideComparisonView installId="install-1" /></MemoryRouter></QueryClientProvider>))
    await settle()
  }
  function button(text: string) {
    const found = Array.from(host.querySelectorAll('button')).find((item) => item.textContent?.includes(text))
    expect(found).toBeTruthy()
    return found!
  }

  it('shows current Base and sparse personal values with a changed marker', async () => {
    getComparison.mockResolvedValue(page())
    await render()
    expect(host.textContent).toContain('new base')
    expect(host.textContent).toContain('mine')
    expect(host.textContent).toContain('nested')
    expect(host.textContent).toContain('Bản gốc đã thay đổi')
    expect(host.textContent).not.toContain('3-Way')
    expect(host.querySelector('a[href="/installed-decks"]')).not.toBeNull()
  })

  it('removes only the chosen override with CAS and refreshes to latest Base', async () => {
    getComparison.mockResolvedValueOnce(page()).mockResolvedValue(page({ overlay_revision: 22, items: [] }))
    resetOverride.mockResolvedValue({ overlay_revision: 22 })
    await render()
    await act(async () => button('Bỏ phần sửa riêng').click())
    await settle()
    expect(resetOverride).toHaveBeenCalledWith('install-1', 'override-1', 21)
    expect(host.textContent).toContain('Bạn chưa có phần sửa riêng')
    expect(host.textContent).not.toContain('mine')
  })

  it('paginates by opaque cursor and retains cached previous pages', async () => {
    getComparison.mockImplementation((_id, cursor) => Promise.resolve(cursor
      ? page({ items: [{ ...page().items[0], id: 'override-2', field_name: 'Reading', operation: 'remove', base_value: null }] })
      : page({ next_cursor: 'opaque-cursor' })))
    await render()
    await act(async () => button('Trang tiếp').click())
    await settle()
    expect(getComparison).toHaveBeenLastCalledWith('install-1', 'opaque-cursor', expect.any(AbortSignal))
    expect(host.textContent).toContain('Reading')
    expect(host.textContent).toContain('Bạn đã xoá giá trị này')
    expect(host.textContent).toContain('null')
    await act(async () => button('Trang trước').click())
    expect(host.textContent).toContain('Meaning')
    expect(getComparison).toHaveBeenCalledTimes(2)
  })

  it('acknowledges the displayed Base while preserving the personal value', async () => {
    getComparison.mockResolvedValueOnce(page()).mockResolvedValue(page({ overlay_revision: 22,
      items: [{ ...page().items[0], base_changed: false }] }))
    keepOverride.mockResolvedValue({ overlay_revision: 22 })
    await render()
    await act(async () => button('Giữ bản của tôi').click())
    await settle()
    expect(keepOverride).toHaveBeenCalledWith('install-1', 'override-1', 21, 'base-hash')
    expect(host.textContent).toContain('mine')
    expect(host.textContent).not.toContain('Bản gốc đã thay đổi')
  })

  it('preserves user edits after a stale revision and reloads comparison', async () => {
    getComparison.mockResolvedValue(page())
    resetOverride.mockRejectedValue(new ApiError('Đã có thay đổi khác.', 409, 'REVISION_CONFLICT'))
    await render()
    await act(async () => button('Bỏ phần sửa riêng').click())
    await settle()
    expect(toastError).toHaveBeenCalled()
    expect(getComparison).toHaveBeenCalledTimes(2)
    expect(host.textContent).toContain('mine')
  })
})

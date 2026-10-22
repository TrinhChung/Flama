// @vitest-environment jsdom
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fetchInstallTemplates, type InstalledDeckTemplate, type InstalledDeckTemplatesResponse } from '@/entities/card-template'
import { InstallTemplatesPage } from '../index'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('@/entities/card-template', async (original) => ({
  ...await original<typeof import('@/entities/card-template')>(),
  fetchInstallTemplates: vi.fn(),
}))
vi.mock('@/features/template-distribution', () => ({
  TemplateDistributionPanel: ({ templateId, origin, onSourceChanged }: { templateId: string; origin: string; onSourceChanged: () => void }) => (
    <div data-distribution-template={templateId} data-origin={origin}>
      <button onClick={onSourceChanged}>Refresh received copy</button>
    </div>
  ),
}))

function template(source: string, name: string): InstalledDeckTemplate {
  return {
    id: `subscription-${source}`, source_template_id: source, local_template_id: `local-${source}`,
    current_version_id: `version-${source}`, update_available: false,
    applied_release: { id: 'shared-v2', version_label: '2.0.0', sequence_no: 2 },
    current_release: { id: 'shared-v2', version_label: '2.0.0', sequence_no: 2 },
    pinned_release: { id: 'deck-v1', version_label: '1.0.0', sequence_no: 1 },
    template: { id: `local-${source}`, name, origin: 'market_copy', current_version_id: `version-${source}` },
  }
}
const response: InstalledDeckTemplatesResponse = {
  install_id: 'install-1', legacy_template_fallback: false,
  deck_release: { id: 'deck-release-1', version_label: '1.0.0', sequence_no: 1 },
  items: [template('source-a', 'Recognition'), template('source-b', 'Listening')],
}
function LocationProbe() {
  const { pathname, search } = useLocation()
  return <output data-location>{pathname}{search}</output>
}

let root: Root
let host: HTMLDivElement
let client: QueryClient
async function flush() {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
}
async function render(path = '/installed-decks/install-1/templates') {
  await act(async () => root.render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes><Route path="/installed-decks/:installId/templates" element={<InstallTemplatesPage />} /></Routes>
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  ))
  await flush()
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchInstallTemplates).mockResolvedValue(structuredClone(response))
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  host = document.createElement('div'); document.body.append(host); root = createRoot(host)
})
afterEach(async () => { await act(async () => root.unmount()); client.clear(); host.remove() })

describe('installed deck template management', () => {
  it('honours a source deep link while editing and updating only the local copy', async () => {
    await render('/installed-decks/install-1/templates?template=source-b')
    expect(fetchInstallTemplates).toHaveBeenCalledWith('install-1', expect.any(AbortSignal))
    expect(host.querySelector('h2')?.textContent).toBe('Listening')
    expect(host.querySelector('a[href="/card-templates/local-source-b"]')).not.toBeNull()
    expect(host.querySelector('[data-distribution-template]')?.getAttribute('data-distribution-template')).toBe('local-source-b')
    expect(host.querySelector('[data-distribution-template]')?.getAttribute('data-origin')).toBe('market_copy')
    expect(host.querySelector('section')?.textContent).toContain('1.0.0')
    expect(host.textContent).toContain('Bộ thẻ vẫn giữ release đã ghim')
    expect(host.querySelector('a[href="/installed-decks"]')).not.toBeNull()
  })

  it('switches templates without losing other query parameters', async () => {
    await render('/installed-decks/install-1/templates?template=source-b&from=dashboard')
    const recognition = Array.from(host.querySelectorAll('nav button')).find((button) => button.textContent?.includes('Recognition')) as HTMLButtonElement
    await act(async () => recognition.click())
    expect(host.querySelector('h2')?.textContent).toBe('Recognition')
    expect(host.querySelector('nav [aria-current="true"]')).toBe(recognition)
    expect(host.querySelector('[data-location]')?.textContent).toContain('template=source-a&from=dashboard')
    expect(host.querySelector('[data-distribution-template]')?.getAttribute('data-distribution-template')).toBe('local-source-a')
  })

  it('explains a stale source deep link and shows the first available copy', async () => {
    await render('/installed-decks/install-1/templates?template=removed')
    expect(host.querySelector('h2')?.textContent).toBe('Recognition')
    expect(host.querySelector('[role="status"]')?.textContent).toContain('không còn thuộc bộ thẻ này')
  })

  it('shows loading until the installation query finishes', async () => {
    let resolve!: (data: InstalledDeckTemplatesResponse) => void
    vi.mocked(fetchInstallTemplates).mockReturnValue(new Promise((done) => { resolve = done }))
    await render()
    expect(host.textContent).toContain('Đang tải template')
    expect(host.querySelector('[data-distribution-template]')).toBeNull()
    await act(async () => resolve(response))
    await flush()
    expect(host.querySelector('h2')?.textContent).toBe('Recognition')
  })

  it('allows retry after an installation error and refetches after a copy update', async () => {
    vi.mocked(fetchInstallTemplates).mockRejectedValueOnce(new Error('Không tìm thấy bộ thẻ đã cài'))
    await render()
    expect(host.querySelector('[role="alert"]')?.textContent).toContain('Không tìm thấy bộ thẻ đã cài')
    const retry = Array.from(host.querySelectorAll('button')).find((button) => button.textContent === 'Thử lại')!
    await act(async () => retry.click())
    await flush()
    expect(host.querySelector('h2')?.textContent).toBe('Recognition')
    await act(async () => (host.querySelector('[data-distribution-template] button') as HTMLButtonElement).click())
    await flush()
    expect(fetchInstallTemplates).toHaveBeenCalledTimes(3)
  })

  it('keeps the legacy warning visible even when there are no received copies', async () => {
    vi.mocked(fetchInstallTemplates).mockResolvedValue({ ...response, items: [], legacy_template_fallback: true })
    await render()
    expect(host.textContent).toContain('chưa lưu bản ghim template')
    expect(host.textContent).toContain('Chưa có template nhận về')
    expect(host.querySelector('a[href="/card-templates"]')).not.toBeNull()
    expect(host.querySelector('[data-distribution-template]')).toBeNull()
  })

  it('does not invent a pinned version for an older release', async () => {
    vi.mocked(fetchInstallTemplates).mockResolvedValue({ ...response, items: [{ ...response.items[0], pinned_release: null }], legacy_template_fallback: true })
    await render()
    expect(host.querySelector('section')?.textContent).toContain('Chưa có bản ghim')
    expect(host.querySelector('section')?.textContent).not.toContain('2.0.0')
  })
})

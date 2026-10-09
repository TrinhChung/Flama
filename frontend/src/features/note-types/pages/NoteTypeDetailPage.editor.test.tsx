// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NoteTypeDetailPage } from './NoteTypeDetailPage'

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn().mockResolvedValue({
      id: 'nt-1',
      name: 'Từ vựng',
      publish_status: 'private',
      field_defs: [
        { id: 'f1', name: 'Kanji', field_type: 'text', position: 0 },
        { id: 'f2', name: 'Meaning', field_type: 'text', position: 1 },
      ],
      templates: [
        {
          id: 't1',
          name: 'Card 1',
          front_html: '{{Kanji}}',
          back_html: '{{Meaning}}',
          shared_css: '.card{}',
        },
      ],
    }),
    mutate: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('../components/NoteTypeLivePreview', () => ({
  NoteTypeLivePreview: () => null,
}))

vi.mock('@/components/ambient-background', () => ({
  AmbientBackground: () => null,
}))

vi.mock('@/shared/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/client')>()
  return {
    ...actual,
    apiRequest: vi.fn().mockResolvedValue({ items: [] }),
  }
})

describe('NoteTypeDetailPage editor DOM specification', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('renders template editor card matching baseline DOM snapshot', async () => {
    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={['/note-types/nt-1']}>
            <Routes>
              <Route path="/note-types/:id" element={<NoteTypeDetailPage />} />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    let heading: HTMLElement | null = null
    for (let i = 0; i < 10; i++) {
      await act(async () => {
        await Promise.resolve()
      })
      heading =
        Array.from(container.querySelectorAll('h3')).find(
          (el) => el.textContent?.trim() === 'Trình Soạn Thảo Template',
        ) ?? null
      if (heading) break
    }

    expect(heading).not.toBeNull()
    const card = heading?.closest('[data-slot="card"]')
    expect(card).not.toBeNull()
    expect(card?.outerHTML).toMatchSnapshot()

    const triggers = card?.querySelectorAll('[data-slot="tabs-trigger"]')
    const backTrigger = Array.from(triggers ?? []).find(
      (el) => el.textContent?.trim() === 'Back HTML',
    ) as HTMLElement | undefined
    expect(backTrigger).toBeDefined()

    await act(async () => {
      backTrigger?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
    })

    expect(card?.outerHTML).toMatchSnapshot('back-tab')
  })
})

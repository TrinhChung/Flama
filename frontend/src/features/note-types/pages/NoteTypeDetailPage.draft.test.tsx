// @vitest-environment jsdom

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NoteTypeDetailPage } from './NoteTypeDetailPage'

type TemplateContent = { front_html: string; back_html: string; shared_css: string }
type TemplateFixture = TemplateContent & { id: string; name: string; is_default: boolean }

const state = vi.hoisted(() => ({
  templates: [] as TemplateFixture[],
  resetContent: {} as TemplateContent,
  get: vi.fn(),
  mutate: vi.fn(),
  rename: vi.fn(),
}))

vi.mock('@/app/api', () => ({ appApi: { get: state.get, mutate: state.mutate } }))
vi.mock('@/shared/api/client', async (original) => ({
  ...await original<typeof import('@/shared/api/client')>(),
  apiRequest: vi.fn().mockResolvedValue({ items: [] }),
  apiJson: state.rename,
}))
vi.mock('../components/NoteTypeLivePreview', () => ({ NoteTypeLivePreview: () => null }))
vi.mock('@/components/ambient-background', () => ({ AmbientBackground: () => null }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

const saved: TemplateContent = {
  front_html: '{{Kanji}}',
  back_html: '{{Meaning}}',
  shared_css: '.card { color: black; }',
}
const second: TemplateContent = {
  front_html: '<h2>{{Meaning}}</h2>',
  back_html: '<p>{{Kanji}}</p>',
  shared_css: '.card { color: blue; }',
}
const draft: TemplateContent = {
  front_html: '<b>UNSAVED FRONT</b>',
  back_html: '<i>UNSAVED BACK</i>',
  shared_css: '.card { color: red; }',
}
const tabs = [
  ['Front HTML', 'front_html'],
  ['Back HTML', 'back_html'],
  ['Shared CSS', 'shared_css'],
] as const

function setValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}

function button(label: string) {
  const found = [...document.querySelectorAll('button')].find(
    (element) => element.textContent?.trim() === label,
  )
  expect(found, `button ${label}`).toBeDefined()
  return found!
}

async function flush() {
  await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
}

describe('NoteTypeDetailPage template drafts', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    state.templates = [
      { id: 't1', name: 'Card 1', is_default: true, ...saved },
      { id: 't2', name: 'Card 2', is_default: false, ...second },
    ]
    state.resetContent = { ...saved }
    state.get.mockImplementation(async () => ({
      id: 'nt-1', name: 'Vocabulary', publish_status: 'private', field_defs: [],
      templates: state.templates.map((template) => ({ ...template })),
    }))
    state.rename.mockImplementation(async (_url: string, _method: string, body: { name: string }) => {
      state.templates[0].name = body.name
      return { ...state.templates[0] }
    })
    state.mutate.mockImplementation(async (path: string, method: string, body?: TemplateContent) => {
      if (path.endsWith('/preview')) return {}
      const template = state.templates.find((item) => path.includes(`/templates/${item.id}`))!
      if (method === 'PATCH') Object.assign(template, body)
      if (path.endsWith('/reset')) Object.assign(template, state.resetContent)
      return { ...template }
    })
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    queryClient.clear()
    container.remove()
    document.body.innerHTML = ''
    vi.restoreAllMocks()
  })

  async function renderPage() {
    await act(async () => root.render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/note-types/nt-1']}>
          <Routes><Route path="/note-types/:id" element={<NoteTypeDetailPage />} /></Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ))
    await flush()
    expect(container.querySelector('textarea')?.value).toBe(saved.front_html)
  }

  async function activateTab(label: string) {
    // Radix selects tabs on focus; a bare jsdom click does not dispatch mousedown/focus.
    await act(async () => button(label).focus())
    expect(button(label).getAttribute('aria-selected')).toBe('true')
  }

  async function editContent(content: TemplateContent) {
    for (const [label, key] of tabs) {
      await activateTab(label)
      await act(async () => setValue(container.querySelector('textarea')!, content[key]))
      expect(container.querySelector('textarea')!.value).toBe(content[key])
    }
  }

  async function expectContent(content: TemplateContent) {
    for (const [label, key] of tabs) {
      await activateTab(label)
      expect(container.querySelector('textarea')!.value).toBe(content[key])
    }
  }

  async function selectTemplate(id: string) {
    await act(async () => {
      const select = container.querySelector('select')!
      select.value = id
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
  }

  it('preserves Front, Back and CSS drafts after metadata-only rename and refetch', async () => {
    await renderPage()
    await editContent(draft)
    await act(async () => button('Đổi tên').click())
    await act(async () => setValue(document.querySelector('#template-name-input')!, 'Renamed'))
    await act(async () => button('Lưu tên').click())
    await flush()

    expect(state.rename).toHaveBeenCalledWith(
      '/api/note-types/nt-1/templates/t1', 'PATCH', { name: 'Renamed' },
    )
    expect(state.get.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(container.querySelector('option[value="t1"]')?.textContent).toBe('Renamed')
    await expectContent(draft)
  })

  it('loads the selected template content when switching away from an unsaved draft', async () => {
    await renderPage()
    await editContent(draft)
    await selectTemplate('t2')
    await expectContent(second)
    await selectTemplate('t1')
    await expectContent(saved)
  })

  it('syncs on template ID change even when both templates have identical saved content', async () => {
    Object.assign(state.templates[1], saved)
    await renderPage()
    await editContent(draft)
    await selectTemplate('t2')
    await expectContent(saved)
  })

  it('syncs genuine server content changes for the same template after refetch', async () => {
    await renderPage()
    await editContent(draft)
    Object.assign(state.templates[0], second)
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: ['note-type-detail', 'nt-1'] })
    })
    await flush()
    await expectContent(second)
  })

  it('saves all draft fields and reloads the persisted content when reselected', async () => {
    await renderPage()
    await editContent(draft)
    await act(async () => button('Lưu Template').click())
    await flush()

    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1/templates/t1', 'PATCH', draft)
    expect(state.get.mock.calls.length).toBeGreaterThanOrEqual(2)
    await expectContent(draft)
    await selectTemplate('t2')
    await selectTemplate('t1')
    await expectContent(draft)
  })

  it.each([
    ['unchanged saved defaults', saved],
    ['different defaults', second],
  ])('resets every draft field to %s', async (_label, defaults) => {
    state.resetContent = { ...defaults }
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    await renderPage()
    await editContent(draft)
    await act(async () => button('Reset').click())
    await flush()

    expect(state.mutate).toHaveBeenCalledWith('/note-types/nt-1/templates/t1/reset', 'POST')
    expect(state.get.mock.calls.length).toBeGreaterThanOrEqual(2)
    await expectContent(defaults)
  })
})

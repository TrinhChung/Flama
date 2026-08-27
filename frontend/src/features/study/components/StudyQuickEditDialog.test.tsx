// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  mutate: vi.fn(),
  get: vi.fn(),
}))

vi.mock('@/app/api', () => ({
  appApi: {
    mutate: mocks.mutate,
    get: mocks.get,
  },
}))

import { StudyQuickEditDialog } from './StudyQuickEditDialog'
import type { StudyContentArtifact, StudyTemplateArtifact } from '../types'

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient

function renderWithClient(ui: React.ReactNode) {
  return (
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

const mockTemplate: StudyTemplateArtifact = {
  schema_version: 'study-template.v1',
  renderer_abi: 'client_v1',
  id: 'tmpl-1',
  version: '1',
  front_source: 'front',
  back_source: 'back',
  front_inline_scripts: [],
  back_inline_scripts: [],
  shared_css: '',
  field_defs: [
    { name: 'Word', field_type: 'text', required: true, position: 0 },
    { name: 'Meaning', field_type: 'text', required: false, position: 1 },
  ],
}

const mockContent: StudyContentArtifact = {
  schema_version: 'study-content.v1',
  renderer_abi: 'client_v1',
  id: 'cnt-1',
  note_id: '101',
  version: '1',
  field_values: {
    Word: '勉強',
    Meaning: 'Học tập',
  },
  render_context: {},
  media: [],
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  mocks.mutate.mockReset()
  mocks.get.mockReset()
  mocks.get.mockResolvedValue({
    card: { card_id: 'card-123', status: 'learning' },
    note: {
      id: '101',
      deck_id: 5,
      deck_name: 'N5 Deck',
      field_values: { Word: '勉強', Meaning: 'Học tập' },
      tags: ['jlpt-n5'],
    },
    fields: [
      { name: 'Word', position: 0, required: true },
      { name: 'Meaning', position: 1, required: false },
    ],
    decks: [{ id: 5, name: 'N5 Deck' }],
  })
  mocks.mutate.mockResolvedValue({ success: true })
})

afterEach(async () => {
  if (root) await act(async () => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? window.HTMLTextAreaElement.prototype
    : window.HTMLInputElement.prototype
  const descriptor = Object.getOwnPropertyDescriptor(prototype, 'value')
  descriptor?.set?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
  element.dispatchEvent(new Event('change', { bubbles: true }))
}

describe('StudyQuickEditDialog', () => {
  it('renders pre-populated field values immediately from study session content', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={true}
            onOpenChange={onOpenChange}
            cardId="card-123"
            deckName="N5 Deck"
            template={mockTemplate}
            content={mockContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    expect(document.body.textContent).toContain('Sửa nhanh thẻ')
    expect(document.body.textContent).toContain('N5 Deck')

    const wordInput = document.querySelector('input[placeholder="Nhập Word…"]') as HTMLInputElement
    expect(wordInput).not.toBeNull()
    expect(wordInput.value).toBe('勉強')

    const meaningTextarea = document.querySelector('textarea[placeholder="Nhập Meaning…"]') as HTMLTextAreaElement
    expect(meaningTextarea).not.toBeNull()
    expect(meaningTextarea.value).toBe('Học tập')
  })

  it('allows adding tags and editing fields, then saving updates card content', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={true}
            onOpenChange={onOpenChange}
            cardId="card-123"
            deckName="N5 Deck"
            template={mockTemplate}
            content={mockContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    const meaningTextarea = document.querySelector('textarea[placeholder="Nhập Meaning…"]') as HTMLTextAreaElement
    await act(async () => {
      setNativeValue(meaningTextarea, 'Học hành, ôn luyện')
    })

    const saveButton = Array.from(document.querySelectorAll('button')).find(
      (btn) => btn.textContent?.includes('Lưu thay đổi'),
    )
    expect(saveButton).toBeDefined()
    expect(saveButton?.hasAttribute('disabled')).toBe(false)

    await act(async () => {
      saveButton?.click()
    })

    expect(mocks.mutate).toHaveBeenCalledWith(
      '/browse/cards/card-123',
      'PATCH',
      expect.objectContaining({
        field_values: expect.objectContaining({
          Word: '勉強',
          Meaning: 'Học hành, ôn luyện',
        }),
      }),
    )

    expect(onCardUpdated).toHaveBeenCalledWith(
      'card-123',
      expect.objectContaining({
        Word: '勉強',
        Meaning: 'Học hành, ôn luyện',
      }),
    )
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('reverts changes when Khôi phục button is clicked', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={true}
            onOpenChange={onOpenChange}
            cardId="card-123"
            deckName="N5 Deck"
            template={mockTemplate}
            content={mockContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    const wordInput = document.querySelector('input[placeholder="Nhập Word…"]') as HTMLInputElement
    await act(async () => {
      setNativeValue(wordInput, 'Changed Word')
    })

    expect(wordInput.value).toBe('Changed Word')

    const revertButton = Array.from(document.querySelectorAll('button')).find(
      (btn) => btn.textContent?.includes('Khôi phục'),
    )
    expect(revertButton).toBeDefined()

    await act(async () => {
      revertButton?.click()
    })

    expect(wordInput.value).toBe('勉強')
  })
})

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
  generateStrokes: vi.fn(),
}))

vi.mock('@/app/api', () => ({
  appApi: {
    mutate: mocks.mutate,
    get: mocks.get,
    generateStrokes: mocks.generateStrokes,
  },
}))

import { StudyQuickEditDialog } from './StudyQuickEditDialog'
import { inferFieldType } from '../hooks/useStudyQuickEditForm'
import type { StudyContentArtifact, StudyTemplateArtifact } from '../types'
import { canonicalDigest } from '../session/canonicalDigest'

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
  mocks.generateStrokes.mockReset()
  mocks.generateStrokes.mockResolvedValue({
    characters: ['勉', '強'],
    items: [],
    output: '',
  })
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
  it('sends the revision captured before the user draft when detail refreshes in the background', async () => {
    const detail = {
      card: { card_id: 'card-123', status: 'learning' },
      note: { id: '101', deck_id: 5, deck_name: 'N5 Deck', tags: ['jlpt-n5'],
        field_values: mockContent.field_values, content_revision: 3, field_schema_revision: 4 },
      fields: mockTemplate.field_defs,
      decks: [{ id: 5, name: 'N5 Deck' }],
    }
    mocks.get.mockResolvedValue(detail)
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => root?.render(renderWithClient(
      <StudyQuickEditDialog open={true} onOpenChange={vi.fn()} cardId="card-123"
        template={mockTemplate} content={mockContent} onCardUpdated={vi.fn()} />,
    )))
    const word = document.querySelector('input[placeholder*="Word"]') as HTMLInputElement
    await act(async () => setNativeValue(word, 'draft'))
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'card-123'], {
      ...detail, note: { ...detail.note, content_revision: 9, field_schema_revision: 10 },
    }))
    const save = Array.from(document.querySelectorAll('button')).find((button) => button.textContent?.includes('Lưu thay đổi'))!
    await act(async () => save.click())
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/cards/card-123', 'PATCH', expect.objectContaining({
      expected_content_revision: 3, expected_field_schema_revision: 4,
    }))
  })

  it('blocks invalid array code and saves nested arrays as native lists', async () => {
    mocks.get.mockImplementation(() => new Promise(() => {}))
    const template = { ...mockTemplate, field_defs: [
      { name: 'Word', field_type: 'text', position: 0 },
      { name: 'Answer', field_type: 'array', position: 1 },
    ] }
    const content = { ...mockContent, field_values: { Word: '勉強', Answer: [['old'], 'answer'] } }
    const onCardUpdated = vi.fn()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => root?.render(renderWithClient(
      <StudyQuickEditDialog open={true} onOpenChange={vi.fn()} cardId="card-123"
        template={template} content={content} onCardUpdated={onCardUpdated} />,
    )))
    const input = document.querySelector<HTMLTextAreaElement>('[aria-label="Answer"]')!
    const save = Array.from(document.querySelectorAll('button')).find((button) => button.textContent?.includes('Lưu thay đổi'))!
    await act(async () => setNativeValue(input, '[1]'))
    expect(save.disabled).toBe(true)
    await act(async () => input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true })))
    expect(mocks.mutate).not.toHaveBeenCalled()
    const values = { Word: '勉強', Answer: [['new'], 'item'] }
    mocks.mutate.mockResolvedValueOnce({ success: true, detail: { note: { id: '101', field_values: values } } })
    await act(async () => setNativeValue(input, JSON.stringify(values.Answer)))
    expect(save.disabled).toBe(false)
    await act(async () => save.click())
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/cards/card-123', 'PATCH', expect.objectContaining({ field_values: values }))
    expect(onCardUpdated).toHaveBeenCalledWith('card-123', values, { noteId: '101', media: undefined })
  })

  it('uses frozen note fields and excludes aliases while authoritative detail is loading', async () => {
    mocks.get.mockImplementation(() => new Promise(() => {}))
    const projection = {
      schema_version: 'template-input-bindings.v1' as const,
      input_bindings: { term: 'field-word' },
      field_defs: [
        { id: 'field-word', name: 'Word', field_type: 'text', required: true, position: 0 },
        { id: 'field-meaning', name: 'Meaning', field_type: 'text', position: 1 },
      ],
    }
    const template = { ...mockTemplate,
      field_defs: [...mockTemplate.field_defs, { id: 'alias-term', name: 'term', field_type: 'text' }],
      binding_projection: { ...projection, fingerprint: canonicalDigest(projection) },
    }
    const content = { ...mockContent, field_values: { Word: 'dog', Meaning: 'animal', term: 'dog' } }
    const onCardUpdated = vi.fn()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyQuickEditDialog open={true} onOpenChange={vi.fn()}
        cardId="card-123" template={template} content={content} onCardUpdated={onCardUpdated} />))
    })
    expect(document.querySelector('input[placeholder*="term"]')).toBeNull()
    expect(document.querySelector('textarea[placeholder*="term"]')).toBeNull()
    const word = document.querySelector('input[placeholder*="Word"]') as HTMLInputElement
    expect(word.value).toBe('dog')
    await act(async () => { setNativeValue(word, 'cat') })
    const save = Array.from(document.querySelectorAll('button')).find((button) => (
      button.textContent?.includes('Lưu thay đổi')
    ))
    await act(async () => { save?.click() })
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/cards/card-123', 'PATCH', expect.objectContaining({
      field_values: { Word: 'cat', Meaning: 'animal' },
    }))
  })

  it('does not use a projected alias as a same-name note value before detail loads', async () => {
    mocks.get.mockImplementation(() => new Promise(() => {}))
    const projection = {
      schema_version: 'template-input-bindings.v1' as const,
      input_bindings: { Word: 'field-meaning' },
      field_defs: [
        { id: 'field-word', name: 'Word', field_type: 'text', position: 0 },
        { id: 'field-meaning', name: 'Meaning', field_type: 'text', position: 1 },
      ],
    }
    const template = { ...mockTemplate, binding_projection: { ...projection, fingerprint: canonicalDigest(projection) } }
    const content = { ...mockContent, field_values: { Word: 'projected meaning', Meaning: 'real meaning' } }
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(renderWithClient(<StudyQuickEditDialog open={true} onOpenChange={vi.fn()}
        cardId="card-123" template={template} content={content} onCardUpdated={vi.fn()} />))
    })
    const word = document.querySelector('input[placeholder*="Word"]') as HTMLInputElement
    expect(word.value).toBe('')
    expect((document.querySelector('textarea[placeholder*="Meaning"]') as HTMLTextAreaElement).value).toBe('real meaning')
  })

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

  it('renders audio player and image preview for media fields in quick edit dialog', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    const mediaTemplate: StudyTemplateArtifact = {
      ...mockTemplate,
      field_defs: [
        { name: 'Word', field_type: 'text', required: true, position: 0 },
        { name: 'Word_Audio', field_type: 'audio', required: false, position: 1 },
        { name: 'Illustration', field_type: 'image', required: false, position: 2 },
      ],
    }

    const mediaContent: StudyContentArtifact = {
      ...mockContent,
      field_values: {
        Word: '猫',
        Word_Audio: 'https://example.com/neko.mp3',
        Illustration: 'https://example.com/neko.png',
      },
    }

    mocks.get.mockResolvedValueOnce({
      card: { card_id: 'card-123', status: 'learning' },
      note: {
        id: '101',
        deck_id: 5,
        deck_name: 'N5 Deck',
        field_values: mediaContent.field_values,
        tags: ['jlpt-n5'],
      },
      fields: mediaTemplate.field_defs,
      decks: [{ id: 5, name: 'N5 Deck' }],
    })

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
            template={mediaTemplate}
            content={mediaContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    // Check Audio Player rendered
    const audioElement = document.querySelector('audio')
    expect(audioElement).not.toBeNull()
    expect(audioElement?.src).toBe('https://example.com/neko.mp3')

    // Check Image preview rendered
    const imageElement = document.querySelector('img[alt="Illustration 1"]') as HTMLImageElement
    expect(imageElement).not.toBeNull()
    expect(imageElement?.src).toBe('https://example.com/neko.png')

    // Check view mode buttons exist for each media field (Preview, URL, Code)
    const previewButtons = document.querySelectorAll('button[title^="Xem trước"]')
    expect(previewButtons.length).toBe(2)
  })

  it('infers audio and image fields by name and resolves assets from media list', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    // Template where field_type was omitted or defaulted to 'text', but field names indicate media
    const implicitMediaTemplate: StudyTemplateArtifact = {
      ...mockTemplate,
      field_defs: [
        { name: 'Word', field_type: 'text', required: true, position: 0 },
        { name: 'Audio', field_type: 'text', required: false, position: 1 },
      ],
    }

    const implicitMediaContent: StudyContentArtifact = {
      ...mockContent,
      field_values: {
        Word: '犬',
        Audio: '[sound:inu.mp3]',
      },
      media: [
        {
          id: 'asset-inu-1',
          field_name: 'Audio',
          filename: 'inu.mp3',
          mime_type: 'audio/mpeg',
          sha256: 'abc123hash',
          proxy_url: '/media/proxy/asset-inu-1',
        },
      ],
    }

    mocks.get.mockResolvedValueOnce({
      card: { card_id: 'card-123', status: 'learning' },
      note: {
        id: '101',
        deck_id: 5,
        deck_name: 'N5 Deck',
        field_values: implicitMediaContent.field_values,
        tags: ['jlpt-n5'],
      },
      fields: implicitMediaTemplate.field_defs,
      decks: [{ id: 5, name: 'N5 Deck' }],
    })

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
            template={implicitMediaTemplate}
            content={implicitMediaContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    // Audio element should be rendered because field is named 'Audio' and resolved via mediaResolver
    const audioElement = document.querySelector('audio')
    expect(audioElement).not.toBeNull()
    expect(audioElement?.src).toContain('/media/proxy/asset-inu-1')
  })

  it('forwards media_assets from PATCH response to onCardUpdated options', async () => {
    const onOpenChange = vi.fn()
    const onCardUpdated = vi.fn()

    mocks.mutate.mockResolvedValueOnce({
      success: true,
      detail: {
        note: {
          id: 789,
          field_values: { Word: '猫', Audio: '/media/proxy/cat-audio-99' },
          tags: ['n5'],
          deck_id: 1,
        },
        media_assets: [
          {
            id: 'cat-audio-99',
            field_name: 'Audio',
            filename: 'cat.mp3',
            mime_type: 'audio/mpeg',
            url: '/media/proxy/cat-audio-99',
          },
        ],
      },
    })

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={true}
            onOpenChange={onOpenChange}
            cardId="card-cat-1"
            deckName="N5 Deck"
            template={mockTemplate}
            content={mockContent}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    // Modify a field to dirty the form
    const wordInput = document.querySelector('input[value="勉強"]') as HTMLInputElement
    expect(wordInput).not.toBeNull()

    await act(async () => {
      setNativeValue(wordInput, '猫')
    })

    // Click Save
    const saveBtn = Array.from(document.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Lưu thay đổi'),
    )
    expect(saveBtn).not.toBeNull()

    await act(async () => {
      saveBtn?.click()
    })

    expect(onCardUpdated).toHaveBeenCalledWith(
      'card-cat-1',
      expect.objectContaining({
        Word: '猫',
        Audio: '/media/proxy/cat-audio-99',
      }),
      expect.objectContaining({
        noteId: '789',
        media: expect.arrayContaining([
          expect.objectContaining({
            id: 'cat-audio-99',
            proxy_url: '/media/proxy/cat-audio-99',
          }),
        ]),
      }),
    )
  })

  it('renders "Tạo nét" button and opens stroke generation modal on click', async () => {
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

    const taoNetButton = Array.from(document.querySelectorAll('button')).find(
      (btn) =>
        btn.textContent?.includes('Tạo nét') ||
        btn.getAttribute('title')?.includes('Tạo sơ đồ thứ tự nét'),
    )
    expect(taoNetButton).toBeDefined()

    await act(async () => {
      taoNetButton?.click()
    })

    expect(document.body.textContent).toContain('Tạo sơ đồ thứ tự nét Kanji & Hanzi')
  })

  it('allows generating strokes and applying them into the card fields', async () => {
    mocks.get.mockResolvedValue({
      card: { card_id: 'card-123', status: 'learning' },
      note: {
        id: '101',
        deck_id: 5,
        deck_name: 'N5 Deck',
        field_values: { Word: '勉強', Meaning: 'Học tập', StrokeDiagram: '' },
        tags: ['jlpt-n5'],
      },
      fields: [
        { name: 'Word', position: 0, required: true },
        { name: 'Meaning', position: 1, required: false },
        { name: 'StrokeDiagram', position: 2, required: false, field_type: 'diagram' },
      ],
      decks: [{ id: 5, name: 'N5 Deck' }],
    })

    mocks.generateStrokes.mockResolvedValue({
      characters: ['勉', '強'],
      items: [
        { char: '勉', hex: '52c9', url: '/static/strokes/ja/52c9.svg' },
        { char: '強', hex: '5f37', url: '/static/strokes/ja/5f37.svg' },
      ],
      output: '/static/strokes/ja/52c9.svg\n/static/strokes/ja/5f37.svg',
    })

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
            template={{
              ...mockTemplate,
              field_defs: [
                ...mockTemplate.field_defs,
                { name: 'StrokeDiagram', field_type: 'diagram', required: false, position: 2 },
              ],
            }}
            content={{
              ...mockContent,
              field_values: {
                ...mockContent.field_values,
                StrokeDiagram: '',
              },
            }}
            onCardUpdated={onCardUpdated}
          />,
        ),
      )
    })

    // Click "Tạo nét"
    const taoNetButton = Array.from(document.querySelectorAll('button')).find(
      (btn) =>
        btn.textContent?.includes('Tạo nét') ||
        btn.getAttribute('title')?.includes('Tạo sơ đồ thứ tự nét'),
    )
    expect(taoNetButton).toBeDefined()

    await act(async () => {
      taoNetButton?.click()
    })

    // Allow stroke modal and preview query to resolve
    await act(async () => {
      await Promise.resolve()
      await new Promise((r) => setTimeout(r, 10))
    })

    expect(document.body.textContent).toContain('Tạo sơ đồ thứ tự nét Kanji & Hanzi')

    // Find "Thêm vào thẻ" button inside the stroke modal
    const applyButton = Array.from(document.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Thêm vào thẻ'),
    )
    expect(applyButton).toBeDefined()

    await act(async () => {
      applyButton?.click()
    })

    // Now save button in Quick Edit Dialog should be enabled (dirty form)
    const saveButton = Array.from(document.querySelectorAll('button')).find((btn) =>
      btn.textContent?.includes('Lưu thay đổi'),
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
          StrokeDiagram: '/static/strokes/ja/52c9.svg\n/static/strokes/ja/5f37.svg',
        }),
      }),
    )
  })

  it('does not crash when closed even if content contains native arrays or unexpected fields', async () => {
    const template = {
      ...mockTemplate,
      field_defs: [
        { name: 'Word', field_type: 'text', position: 0 },
        { name: 'Synonyms', field_type: 'text', position: 1 },
      ],
    }
    const content = {
      ...mockContent,
      field_values: {
        Word: '本',
        Synonyms: ['ほん', '書籍', ['sub-item']],
        ExtraObj: { custom: true },
        ExtraNum: 42,
      },
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    // Should mount and unmount cleanly with open={false} without throwing TypeError
    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={false}
            onOpenChange={vi.fn()}
            cardId="card-123"
            template={template}
            content={content}
            onCardUpdated={vi.fn()}
          />,
        ),
      )
    })

    expect(container.querySelector('[role="dialog"]')).toBeNull()
  })

  it('does not crash when transitioning to session completion with card and template null', async () => {
    const content = {
      ...mockContent,
      field_values: {
        Word: '車',
        Tags: ['n5', 'transport'],
      },
    }

    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    // Replicates completion state where cardId and template become null/undefined
    await act(async () => {
      root?.render(
        renderWithClient(
          <StudyQuickEditDialog
            open={false}
            onOpenChange={vi.fn()}
            cardId={undefined}
            template={null}
            content={content}
            onCardUpdated={vi.fn()}
          />,
        ),
      )
    })

    expect(container.querySelector('[role="dialog"]')).toBeNull()
  })
})

describe('inferFieldType', () => {
  it('does not throw for string, string[], nested arrays, null, undefined, numbers, and objects', () => {
    expect(() => inferFieldType(undefined, undefined, undefined)).not.toThrow()
    expect(() => inferFieldType(null, null, null)).not.toThrow()
    expect(() => inferFieldType('text', 'notes', ['item1', 'item2'])).not.toThrow()
    expect(() => inferFieldType('text', 'nested', [['a', 'b'], ['c']])).not.toThrow()
    expect(() => inferFieldType('text', 'count', 123)).not.toThrow()
    expect(() => inferFieldType('text', 'meta', { key: 'value' })).not.toThrow()
    expect(() => inferFieldType({ invalid: true } as any, 123 as any, ['a'])).not.toThrow()
  })

  it('correctly returns array for native lists and nested lists', () => {
    expect(inferFieldType('array', 'any_name', 'any_val')).toBe('array')
    expect(inferFieldType('text', 'custom_name', ['item 1', 'item 2'])).toBe('array')
    expect(inferFieldType(undefined, 'custom_name', [['nested']])).toBe('array')
  })

  it('correctly infers audio and image fields', () => {
    expect(inferFieldType('text', 'audio_file', 'test.mp3')).toBe('audio')
    expect(inferFieldType('text', 'custom', '[sound:word.mp3]')).toBe('audio')
    expect(inferFieldType('text', 'my_picture', 'image.png')).toBe('image')
    expect(inferFieldType('text', 'custom', 'photo.webp')).toBe('image')
  })

  it('defaults to text for other types without throwing', () => {
    expect(inferFieldType('text', 'Meaning', 'Học tập')).toBe('text')
    expect(inferFieldType(undefined, undefined, 42)).toBe('text')
    expect(inferFieldType(null, null, null)).toBe('text')
  })
})

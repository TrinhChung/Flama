// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowseCardEditForm } from '../components/BrowseCardEditForm'
import { BrowseCardCreateForm } from '../components/BrowseCardCreateForm'
import { useBrowseState } from './useBrowseState'
import type { CardDetailResponse } from '../types'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({ get: vi.fn(), mutate: vi.fn(), sync: vi.fn() }))
vi.mock('@/features/browse/api/browseApi', () => ({
  browseQueryKeys: { noteTypes: ['note-types', 'browse', 'compact'] },
  browseApi: {
    fetchDecks: () => mocks.get('/browse/decks'),
    fetchNoteTypes: () => mocks.get('/note-types', { compact: 1 }),
    fetchCards: (params: unknown) => mocks.get('/browse/cards', params),
    fetchCardDetail: (id: string) => mocks.get(`/browse/cards/${id}`),
    createNote: (body: unknown) => mocks.mutate('/notes', 'POST', body),
    updateCard: (id: string, body: unknown) => mocks.mutate(`/browse/cards/${id}`, 'PATCH', body),
    deleteNote: (id: string) => mocks.mutate(`/browse/notes/${id}`, 'DELETE'),
    deleteNotes: (ids: string[]) => mocks.mutate('/browse/notes/batch-delete', 'POST', { note_ids: ids }),
    generateVoiceVox: (body: unknown) => mocks.mutate('/browse/voicevox/generate', 'POST', body),
    fetchVoiceVoxProfile: () => mocks.get('/api/tts/providers/voicevox/profile'),
    saveVoiceVoxProfile: (body: unknown) => mocks.mutate('/api/tts/providers/voicevox/profile', 'PUT', body),
    fetchVoiceVoxVoices: (api_key: string) => mocks.mutate('/api/tts/providers/voicevox/voices', 'POST', { api_key }),
  },
}))
vi.mock('@/shared/api/bootstrap', () => ({
  bootstrapQueryKey: ['bootstrap'],
  useBootstrap: () => ({ data: { user: { is_admin: false } } }),
}))
vi.mock('@/entities/flashcard/contentUpdates', () => ({ updateCardFieldValues: mocks.sync }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

function makeDetail(cardId: string): CardDetailResponse {
  return {
    card: { card_id: cardId, note_id: `note-${cardId}`, deck_id: 1, deck_name: 'Deck', word: '猫', reading: '', meaning: '', tags: [], status: 'new', due_label: '' },
    note: { id: `note-${cardId}`, note_type_id: 'type', deck_id: 1, deck_name: 'Deck', field_values: { Word: '猫', Answer: [['a', 'b'], ['c']], Notes: '' }, tags: [] },
    fields: [{ name: 'Word', position: 0, field_type: 'text' }, { name: 'Answer', position: 1, field_type: 'array' }, { name: 'Notes', position: 2, field_type: 'markdown' }],
  }
}

describe('Browse field editing and persistence', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient
  let browse: ReturnType<typeof useBrowseState>
  let details: Record<string, CardDetailResponse>

  function Harness() {
    browse = useBrowseState()
    const props = { browse, isMobile: false, editorWidth: 400, onMouseDownResize: vi.fn() }
    return browse.isCreatingCard
      ? <BrowseCardCreateForm {...props} />
      : <BrowseCardEditForm key={browse.activeCardId} {...props} />
  }

  async function waitFor(check: () => boolean) {
    for (let attempt = 0; attempt < 100 && !check(); attempt++) {
      await act(async () => { await new Promise((resolve) => setTimeout(resolve, 10)) })
    }
    expect(check()).toBe(true)
  }

  function button(text: string) {
    return Array.from(container.querySelectorAll('button')).find((item) => item.textContent?.includes(text))!
  }

  function setInputValue(input: HTMLInputElement, value: string) {
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')!.set!.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }

  function tagInput() {
    return container.querySelector<HTMLInputElement>('input[placeholder="Tag mới…"]')!
  }

  async function pressEnter(input: HTMLInputElement, init: KeyboardEventInit = {}) {
    await act(async () => input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, ...init })))
  }

  async function typeArray(value: string) {
    const textarea = container.querySelector<HTMLTextAreaElement>('[aria-label="Answer"]')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, value)
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
  }

  beforeEach(async () => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.sync.mockResolvedValue(undefined)
    details = { A: makeDetail('A'), B: makeDetail('B') }
    mocks.get.mockImplementation(async (path: string) => {
      if (path === '/browse/decks') return { decks: [{ id: 1, name: 'Deck', note_type_id: 'type' }] }
      if (path === '/note-types') return { items: [{ id: 'type', name: 'Type', field_defs: details.A.fields }] }
      if (path === '/browse/cards') return { items: [details.A.card, details.B.card], page: 1, total: 2, pages: 1, has_next: false }
      return details[path.split('/').at(-1)!]
    })
    mocks.mutate.mockImplementation(async (path: string, _method: string, payload: { field_values: Record<string, unknown> }) => {
      const id = path.split('/').at(-1)!
      const next = { ...details[id], note: { ...details[id].note, field_values: { ...details[id].note.field_values, ...payload.field_values } } }
      details[id] = next
      return { success: true, detail: next }
    })
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    await act(async () => root.render(
      <QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/browse?card_id=A']}><Harness /></MemoryRouter></QueryClientProvider>,
    ))
    await waitFor(() => browse.initialFieldValues.Word === '猫')
  })

  afterEach(() => {
    act(() => root.unmount())
    queryClient.clear()
    container.remove()
  })

  it('canonicalizes an old Card bookmark before editor and tool actions', async () => {
    const canonical = { ...details.A, card: { ...details.A.card, card_id: 'note-A' } }
    details['note-A'] = canonical
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], canonical))
    await waitFor(() => browse.activeCardId === 'note-A' && browse.cardDetailQuery.data?.card.card_id === 'note-A')
    expect(browse.editFieldValues.Answer).toEqual([['a', 'b'], ['c']])
    expect(browse.isDirty).toBe(false)
  })

  it('isolates compact note types from the full cache and retains broad invalidation', async () => {
    const fullResponse = { items: [{ id: 'other', name: 'Full response', field_defs: [] }] }
    await act(async () => queryClient.setQueryData(['note-types'], fullResponse))
    expect(browse.noteTypesQuery.data?.items[0].id).toBe('type')
    expect(browse.noteTypesQuery.data?.items[0].field_defs).toEqual(details.A.fields)
    expect(queryClient.getQueryData(['note-types'])).toBe(fullResponse)
    const previousCalls = mocks.get.mock.calls.filter(([path]) => path === '/note-types').length
    await act(async () => { await queryClient.invalidateQueries({ queryKey: ['note-types'] }) })
    expect(mocks.get.mock.calls.filter(([path]) => path === '/note-types')).toHaveLength(previousCalls + 1)
    expect(mocks.get).toHaveBeenCalledWith('/note-types', { compact: 1 })
    expect(browse.noteTypesQuery.data?.items[0].field_defs?.[1].field_type).toBe('array')
  })

  it('reuses the editor detail when opening a tool for the same Note', async () => {
    const previousGet = mocks.get.getMockImplementation()!
    mocks.get.mockImplementation(async (path: string, ...args: unknown[]) => {
      if (path === '/api/tts/providers/voicevox/profile') return { profile: {} }
      return previousGet(path, ...args)
    })
    const requestsBefore = mocks.get.mock.calls.filter(([path]) => path === '/browse/cards/A').length
    await act(async () => {
      browse.setActiveCardId(null)
      browse.setIsTtsModalOpen(true)
    })
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)) })
    expect(mocks.get.mock.calls.filter(([path]) => path === '/browse/cards/A')).toHaveLength(requestsBefore)
    expect(queryClient.getQueryData(['browse', 'card-detail', 'A'])).toBeDefined()
  })

  it('sends only changed fields and retains an untouched native nested list', async () => {
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: '犬' })))
    await act(async () => button('Lưu').click())
    await waitFor(() => mocks.sync.mock.calls.length === 1)
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/cards/A', 'PATCH', { field_values: { Word: '犬' }, deck_id: 1, tags: [] })
    expect(browse.editFieldValues.Answer).toEqual([['a', 'b'], ['c']])
    expect(browse.isDirty).toBe(false)
  })

  it('saves JSON code as a native list and syncs the server response to Study', async () => {
    const value = [['x', 'y'], '', 'x']
    const typedValue = [[' x ', 'y'], '', 'x']
    mocks.mutate.mockImplementationOnce(async () => {
      details.A = { ...details.A, note: { ...details.A.note, field_values: { ...details.A.note.field_values, Answer: value } } }
      return { success: true, detail: details.A }
    })
    await typeArray(JSON.stringify(typedValue))
    await act(async () => button('Lưu').click())
    await waitFor(() => mocks.sync.mock.calls.length === 1)
    expect(mocks.mutate.mock.calls[0][2].field_values).toEqual({ Answer: typedValue })
    expect(mocks.sync).toHaveBeenCalledWith({ cardId: 'A', noteId: 'note-A', fieldValues: details.A.note.field_values })
    expect(browse.editFieldValues.Answer).toEqual(value)
    expect(browse.isDirty).toBe(false)
  })

  it('blocks Save and Ctrl+Enter for invalid JSON, then restores the original array on revert', async () => {
    await typeArray('[{"unsupported": true}]')
    expect(button('Lưu').disabled).toBe(true)
    await act(async () => container.firstElementChild!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true })))
    expect(mocks.mutate).not.toHaveBeenCalled()
    await act(async () => browse.handleRevert())
    expect(JSON.parse(container.querySelector<HTMLTextAreaElement>('[aria-label="Answer"]')!.value)).toEqual([['a', 'b'], ['c']])
    expect(browse.isDirty).toBe(false)
    expect(container.querySelector('[role="alert"]')).toBeNull()
  })

  it('keeps unsaved fields when the detail query receives a background refresh', async () => {
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'draft' })))
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], { ...details.A, note: { ...details.A.note, field_values: { ...details.A.note.field_values, Word: 'server' } } }))
    await waitFor(() => browse.cardDetailQuery.data?.note.field_values.Word === 'server')
    expect(browse.editFieldValues.Word).toBe('draft')
    expect(browse.initialFieldValues.Word).toBe('猫')
  })

  it('sends revisions captured with the editable values despite a background refresh', async () => {
    details.A = { ...details.A, note: { ...details.A.note, content_revision: 3, field_schema_revision: 4 } }
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], details.A))
    await waitFor(() => browse.cardDetailQuery.data?.note.content_revision === 3)
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'draft' })))
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], {
      ...details.A, note: { ...details.A.note, content_revision: 9, field_schema_revision: 6 },
    }))
    await act(async () => button('Lưu').click())
    await waitFor(() => mocks.mutate.mock.calls.length === 1)
    expect(mocks.mutate.mock.calls[0][2]).toMatchObject({
      expected_content_revision: 3, expected_field_schema_revision: 4,
    })
  })

  it('uses only the captured install overlay revision for cloned edits', async () => {
    details.A = { ...details.A, note: { ...details.A.note, deck_install_id: 'install', overlay_revision: 7,
      content_revision: 90, field_schema_revision: 80 } }
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], details.A))
    await waitFor(() => browse.cardDetailQuery.data?.note.overlay_revision === 7)
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'clone draft' })))
    await act(async () => button('Lưu').click())
    await waitFor(() => mocks.mutate.mock.calls.length === 1)
    expect(mocks.mutate.mock.calls[0][2].expected_overlay_revision).toBe(7)
    expect(mocks.mutate.mock.calls[0][2]).not.toHaveProperty('expected_content_revision')
    expect(mocks.mutate.mock.calls[0][2]).not.toHaveProperty('expected_field_schema_revision')
  })

  it('syncs the saved card even if another card is selected before the response arrives', async () => {
    let finish!: (value: { detail: CardDetailResponse }) => void
    mocks.mutate.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'saved A' })))
    await act(async () => button('Lưu').click())
    await act(async () => browse.setActiveCardId('B'))
    await waitFor(() => browse.cardDetailQuery.data?.card.card_id === 'B' && browse.editFieldValues.Word === '猫')
    const committed = { ...details.A, note: { ...details.A.note, field_values: { ...details.A.note.field_values, Word: 'canonical A' } } }
    await act(async () => finish({ detail: committed }))
    await waitFor(() => mocks.sync.mock.calls.length === 1)
    expect(mocks.sync).toHaveBeenCalledWith({ cardId: 'A', noteId: 'note-A', fieldValues: committed.note.field_values })
    expect(browse.editFieldValues.Word).toBe('猫')
    expect(browse.isDirty).toBe(false)
  })

  it('creates native arrays and uses a multiline editor for markdown fields', async () => {
    await act(async () => browse.handleStartCreateCard())
    expect(container.querySelectorAll('textarea').length).toBe(2)
    await act(async () => browse.setEditFieldValues({ Word: 'new', Answer: '[ ["one", "two"], "three" ]' }))
    mocks.mutate.mockResolvedValueOnce({ id: 'new-note' })
    await act(async () => button('Tạo').click())
    await waitFor(() => mocks.mutate.mock.calls.length === 1)
    expect(mocks.mutate).toHaveBeenCalledWith('/notes', 'POST', { deck_id: 1, note_type_id: 'type', field_values: { Word: 'new', Answer: [['one', 'two'], 'three'] }, tags: [] })
  })

  it('preserves a newer draft while synchronizing the committed values after an in-flight save', async () => {
    let finish!: (value: { detail: CardDetailResponse }) => void
    mocks.mutate.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'submitted' })))
    await act(async () => button('Lưu').click())
    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'newer draft' })))
    details.A = { ...details.A, note: { ...details.A.note, field_values: { ...details.A.note.field_values, Word: 'submitted' } } }
    await act(async () => finish({ detail: details.A }))
    await waitFor(() => mocks.sync.mock.calls.length === 1)
    expect(browse.editFieldValues.Word).toBe('newer draft')
    expect(browse.initialFieldValues.Word).toBe('submitted')
    expect(browse.isDirty).toBe(true)
    expect(mocks.sync.mock.calls[0][0].fieldValues.Word).toBe('submitted')
  })

  it('blocks creation with an invalid Code draft', async () => {
    await act(async () => browse.handleStartCreateCard())
    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Xem code Answer"]')!.click())
    await typeArray('["unfinished"')
    expect(button('Tạo').disabled).toBe(true)
    await act(async () => container.firstElementChild!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', ctrlKey: true, bubbles: true })))
    expect(mocks.mutate).not.toHaveBeenCalled()
  })

  it('deletes the selected Note rather than its preview Card', async () => {
    mocks.mutate.mockResolvedValueOnce({ success: true, deleted_count: 1 })
    await act(async () => browse.deleteMutation.mutateAsync('A'))
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/notes/note-A', 'DELETE')
    expect(browse.activeCardId).toBeNull()
  })

  it('bulk deletes Note IDs and retains selected identities across pages', async () => {
    await act(async () => browse.setSelectedCards(['A']))
    await act(async () => browse.setPage(2))
    mocks.get.mockImplementation(async (path: string) => {
      if (path === '/browse/cards') return { items: [details.B.card], page: 2, total: 2, pages: 2 }
      if (path === '/browse/decks') return { decks: [{ id: 1, name: 'Deck' }] }
      if (path === '/note-types') return { items: [] }
      return details[path.split('/').at(-1)!]
    })
    await act(async () => queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] }))
    await waitFor(() => browse.cards.length === 1)
    await act(async () => browse.setSelectedCards(['A', 'B']))
    mocks.mutate.mockResolvedValueOnce({ success: true, deleted_count: 2 })
    await act(async () => browse.bulkDeleteMutation.mutateAsync(['A', 'B']))
    expect(mocks.mutate).toHaveBeenCalledWith('/browse/notes/batch-delete', 'POST',
      { note_ids: ['note-A', 'note-B'] })
    expect(browse.selectedCards).toEqual([])
  })

  it('keeps the same focused text input while typing past 50 characters', async () => {
    const word = Array.from(container.querySelectorAll('input')).find((input) => input.value === '猫')!
    word.focus()
    for (let length = 2; length <= 60; length++) {
      await act(async () => setInputValue(word, '猫'.repeat(length)))
      expect(document.activeElement).toBe(word)
    }
    expect(word.isConnected).toBe(true)
    expect(word.tagName).toBe('INPUT')
    expect(browse.editFieldValues.Word).toBe('猫'.repeat(60))
  })

  it('ignores the Enter that confirms an IME candidate and dedupes tags like the backend', async () => {
    const input = tagInput()
    expect(input.maxLength).toBe(64)
    await act(async () => setInputValue(input, 'にほんご'))
    await pressEnter(input, { isComposing: true })
    expect(browse.editTags).toEqual([])
    expect(input.value).toBe('にほんご')

    await pressEnter(input)
    expect(browse.editTags).toEqual(['にほんご'])

    await act(async () => setInputValue(input, 'Food'))
    await pressEnter(input)
    await act(async () => setInputValue(input, 'FOOD'))
    await pressEnter(input)
    expect(browse.editTags).toEqual(['にほんご', 'Food'])
  })

  it('stops adding tags at the backend limit of 50', async () => {
    const fifty = Array.from({ length: 50 }, (_, index) => `t${index}`)
    await act(async () => browse.setEditTags(fifty))
    await act(async () => setInputValue(tagInput(), 'one-more'))
    await pressEnter(tagInput())
    expect(browse.editTags).toHaveLength(50)
  })

  it('locks deck, tags and image uploads for a cloned card and leaves them out of the save', async () => {
    details.A = {
      ...details.A,
      note: { ...details.A.note, deck_install_id: 'install', overlay_revision: 2, tags: ['shared'],
        field_values: { ...details.A.note.field_values, Picture: '' } },
      fields: [...details.A.fields, { name: 'Picture', position: 3, field_type: 'image' }],
      can_upload_media: false,
    }
    await act(async () => queryClient.setQueryData(['browse', 'card-detail', 'A'], details.A))
    await waitFor(() => browse.isCloneCard && browse.editTags.includes('shared'))

    expect(container.querySelector('select')!.disabled).toBe(true)
    expect(tagInput().disabled).toBe(true)
    expect(container.textContent).toContain('không thể chuyển deck, sửa tag hay tải ảnh lên')
    expect(container.textContent).toContain('Thẻ này không hỗ trợ tải ảnh lên')
    expect(Array.from(container.querySelectorAll('button')).some((item) => item.closest('[data-slot="badge"]'))).toBe(false)

    await act(async () => browse.setEditFieldValues((previous) => ({ ...previous, Word: 'clone edit' })))
    await act(async () => button('Lưu').click())
    await waitFor(() => mocks.mutate.mock.calls.length === 1)
    expect(mocks.mutate.mock.calls[0][2]).not.toHaveProperty('deck_id')
    expect(mocks.mutate.mock.calls[0][2]).not.toHaveProperty('tags')
    expect(mocks.mutate.mock.calls[0][2].field_values).toEqual({ Word: 'clone edit' })
  })

  it('does not request VoiceVox voices again for every API key keystroke', async () => {
    mocks.mutate.mockImplementation(async (path: string) => (path.endsWith('/voices') ? { items: [] } : { success: true }))
    const baseGet = mocks.get.getMockImplementation()!
    mocks.get.mockImplementation(async (path: string, params?: unknown) =>
      path.endsWith('/voicevox/profile') ? { profile: { has_api_key: false, key_status: 'missing' } } : baseGet(path, params))
    const voiceRequests = () => mocks.mutate.mock.calls.filter(([path]) => String(path).endsWith('/voices')).length

    await act(async () => browse.setIsTtsModalOpen(true))
    await waitFor(() => voiceRequests() === 1)
    for (const key of ['a', 'ab', 'abc']) {
      await act(async () => browse.setTtsApiKey(key))
    }
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 30)) })
    expect(voiceRequests()).toBe(1)
  })
})

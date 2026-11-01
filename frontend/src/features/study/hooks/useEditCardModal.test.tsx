// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useEditCardModal, type EditCardModalProps } from './useEditCardModal'

const mocks = vi.hoisted(() => ({ stage: vi.fn(), save: vi.fn(), updateSession: vi.fn() }))
vi.mock('@/entities/flashcard', () => ({ stageNoteMedia: mocks.stage }))
vi.mock('@/shared/api/client', () => ({ apiJson: mocks.save }))
vi.mock('../session/sessionStore', () => ({ updateCardFieldValuesInSessions: mocks.updateSession }))

describe('card edit media lifecycle', () => {
  let root: Root | undefined
  let container: HTMLDivElement | undefined
  let editor: ReturnType<typeof useEditCardModal>

  afterEach(() => {
    if (root) act(() => root?.unmount())
    container?.remove()
    vi.clearAllMocks()
  })

  async function renderEditor(overrides: Partial<EditCardModalProps> = {}) {
    const props: EditCardModalProps = {
      opened: true, onClose: vi.fn(), cardId: 'card-1', noteId: 'note-1',
      fieldDefs: [{ name: 'Image', field_type: 'image' }],
      initialFieldValues: { Image: '/store/existing' }, initialTags: [], ...overrides,
    }
    function Harness() { editor = useEditCardModal(props); return null }
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => root!.render(<Harness />))
    return props
  }

  it('keeps uploaded media staged until Save and refreshes sessions from committed URLs', async () => {
    const previewUrl = 'https://media.example.test/media/staged/stg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    mocks.stage.mockResolvedValue({ url: previewUrl })
    const committed = { success: true, field_values: { Image: '/store/committed-db-id' } }
    mocks.save.mockResolvedValue(committed)
    const props = await renderEditor()
    const file = new File(['raw'], 'image.png', { type: 'image/png' })
    await act(async () => editor.handleMediaUpload('Image', file))
    expect(mocks.stage).toHaveBeenCalledWith(file, 'image.png', { noteId: 'note-1', fieldName: 'Image' }, expect.any(AbortSignal))
    expect(mocks.save).not.toHaveBeenCalled()
    expect(editor.fieldValues.Image).toBe(previewUrl)
    await act(async () => editor.handleSave())
    expect(mocks.save).toHaveBeenCalledWith('/api/study/cards/card-1/edit', 'PATCH', expect.objectContaining({ field_values: { Image: previewUrl } }))
    expect(mocks.updateSession).toHaveBeenCalledWith('card-1', committed.field_values, { noteId: 'note-1' })
    expect(props.onSaved).toBeUndefined()
    expect(props.onClose).toHaveBeenCalledOnce()
  })

  it('retains the previous field when staging fails and performs no save', async () => {
    mocks.stage.mockRejectedValue(new Error('Media worker unavailable'))
    await renderEditor()
    await act(async () => editor.handleMediaUpload('Image', new File(['raw'], 'image.png')))
    expect(editor.fieldValues.Image).toBe('/store/existing')
    expect(editor.error).toBe('Media worker unavailable')
    expect(mocks.save).not.toHaveBeenCalled()
  })
})

// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { updateCardFieldValues } from '@/entities/flashcard/model/cardContentUpdates'

const mocks = vi.hoisted(() => ({ persist: vi.fn() }))
vi.mock('@/features/study/contentUpdates', () => ({
  updateCardFieldValuesInSessions: mocks.persist,
}))
import './studyContentSync'

afterEach(() => vi.clearAllMocks())

describe('app card content persistence binding', () => {
  it('awaits headless persistence without mounting a Study page or event listener', async () => {
    let finish!: () => void
    mocks.persist.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
    const completed = vi.fn()
    const update = updateCardFieldValues({
      cardId: 'card-1', noteId: 'note-1', fieldValues: { Audio: '/media/proxy/audio-1' },
    }).then(completed)

    await vi.waitFor(() => expect(mocks.persist).toHaveBeenCalledOnce())
    expect(mocks.persist).toHaveBeenCalledWith('card-1', { Audio: '/media/proxy/audio-1' }, {
      noteId: 'note-1', media: undefined,
    })
    expect(completed).not.toHaveBeenCalled()
    finish()
    await update
    expect(completed).toHaveBeenCalledOnce()
  })

  it('propagates a persistence failure to the caller', async () => {
    mocks.persist.mockRejectedValueOnce(new Error('storage failed'))
    await expect(updateCardFieldValues({ cardId: 'card-1', fieldValues: {} })).rejects.toThrow('storage failed')
  })
})

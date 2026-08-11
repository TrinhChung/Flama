import { afterEach, describe, expect, it, vi } from 'vitest'
import { appApi } from '@/app/api'
import { loadDeckOptionsForPublish } from './publishApi'

describe('loadDeckOptionsForPublish', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('loads publish eligibility options from the shared-deck API', async () => {
    const getSpy = vi.spyOn(appApi, 'get').mockResolvedValue({
      items: [
        {
          id: 42,
          name: 'JLPT N1',
          parent_id: null,
          card_count: 170,
          is_selectable: true,
          block_code: null,
          block_reason: null,
          shared_item_id: null,
        },
      ],
    })

    await expect(loadDeckOptionsForPublish()).resolves.toEqual({
      items: [
        {
          id: 42,
          name: 'JLPT N1',
          parent_id: null,
          card_count: 170,
          is_selectable: true,
          block_code: null,
          block_reason: null,
          shared_item_id: null,
        },
      ],
    })
    expect(getSpy).toHaveBeenCalledOnce()
    expect(getSpy).toHaveBeenCalledWith('/api/shared/decks/publish-options')
  })
})

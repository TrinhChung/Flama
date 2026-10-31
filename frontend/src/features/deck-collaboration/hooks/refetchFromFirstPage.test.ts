import { QueryClient, type InfiniteData } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { refetchFromFirstPage } from './refetchFromFirstPage'

describe('refetchFromFirstPage', () => {
  it('drops loaded pages after the first before refetching', async () => {
    const client = new QueryClient()
    const key = ['deck-change-request', 'request-1']
    client.setQueryData<InfiniteData<string, string | null>>(key, {
      pages: ['page 1', 'page 2', 'page 3'],
      pageParams: [null, 'cursor-2', 'cursor-3'],
    })
    await refetchFromFirstPage(client, ['deck-change-request'])
    expect(client.getQueryData(key)).toEqual({ pages: ['page 1'], pageParams: [null] })
    expect(client.getQueryState(key)?.isInvalidated).toBe(true)
  })
})

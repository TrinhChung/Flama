import { describe, expect, it, vi } from 'vitest'
import { createDeckSummaryLoader } from './deckSummaryLoader'

const mocks = vi.hoisted(() => ({ fetch: vi.fn() }))
vi.mock('./browseApi', () => ({ browseApi: { fetchDeckSummaries: mocks.fetch } }))

describe('shared deck summary cancellation', () => {
  it('keeps a shared request alive when only one deck consumer cancels', async () => {
    let finish!: (value: { decks: Array<{ id: number; name: string }> }) => void
    mocks.fetch.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    const load = createDeckSummaryLoader()
    const first = new AbortController()
    const second = new AbortController()
    const canceled = load(1, first.signal).catch((error: DOMException) => error.name)
    const retained = load(2, second.signal)
    await Promise.resolve()
    const signal = mocks.fetch.mock.calls.at(-1)![1] as AbortSignal
    first.abort()
    expect(await canceled).toBe('AbortError')
    expect(signal.aborted).toBe(false)
    finish({ decks: [{ id: 1, name: 'First' }, { id: 2, name: 'Second' }] })
    await expect(retained).resolves.toMatchObject({ id: 2, summary_loaded: true })
  })

  it('aborts the shared request after every deck consumer cancels', async () => {
    mocks.fetch.mockImplementationOnce((_ids: number[], signal: AbortSignal) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => reject(new DOMException('Canceled', 'AbortError')), { once: true })
    }))
    const load = createDeckSummaryLoader()
    const first = new AbortController()
    const second = new AbortController()
    const results = [load(1, first.signal), load(2, second.signal)].map((request) => request.catch((error: DOMException) => error.name))
    await Promise.resolve()
    const signal = mocks.fetch.mock.calls.at(-1)![1] as AbortSignal
    first.abort()
    expect(signal.aborted).toBe(false)
    second.abort()
    expect(signal.aborted).toBe(true)
    expect(await Promise.all(results)).toEqual(['AbortError', 'AbortError'])
  })
})

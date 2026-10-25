import { browseApi } from './browseApi'
import type { BrowseDeck } from '../types'

type PendingSummary = {
  id: number
  signal: AbortSignal
  resolve: (deck: BrowseDeck) => void
  reject: (error: unknown) => void
}

/** Per-deck cache identities, bounded network batches, and shared cancellation. */
export function createDeckSummaryLoader() {
  let pending: PendingSummary[] = []
  let active = 0
  let scheduled = false

  const flush = () => {
    scheduled = false
    pending = pending.filter((item) => !item.signal.aborted)
    while (active < 2 && pending.length > 0) {
      const batch = pending.splice(0, 50)
      const controller = new AbortController()
      const onAbort = () => {
        if (batch.every((item) => item.signal.aborted)) controller.abort()
      }
      batch.forEach((item) => item.signal.addEventListener('abort', onAbort, { once: true }))
      active += 1
      void browseApi.fetchDeckSummaries(batch.map((item) => item.id), controller.signal)
        .then(({ decks }) => {
          const byId = new Map(decks.map((deck) => [deck.id, deck]))
          batch.forEach((item) => {
            if (item.signal.aborted) return
            const deck = byId.get(item.id)
            if (deck) item.resolve({ ...deck, summary_loaded: true })
            else item.reject(new Error(`Missing deck summary: ${item.id}`))
          })
        })
        .catch((error: unknown) => batch.forEach((item) => item.reject(error)))
        .finally(() => {
          batch.forEach((item) => item.signal.removeEventListener('abort', onAbort))
          active -= 1
          flush()
        })
    }
  }

  return (id: number, signal: AbortSignal) => new Promise<BrowseDeck>((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Canceled', 'AbortError')); return }
    const onAbort = () => {
      pending = pending.filter((item) => item.signal !== signal)
      reject(new DOMException('Canceled', 'AbortError'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    const cleanup = () => signal.removeEventListener('abort', onAbort)
    pending.push({ id, signal,
      resolve: (deck) => { cleanup(); resolve(deck) },
      reject: (error) => { cleanup(); reject(error) },
    })
    if (!scheduled) { scheduled = true; queueMicrotask(flush) }
  })
}

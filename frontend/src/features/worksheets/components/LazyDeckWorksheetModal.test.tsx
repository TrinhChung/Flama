// @vitest-environment jsdom

import { act, useState, type ComponentType } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeckWorksheetModalProps } from './DeckWorksheetModal'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve
    reject = onReject
  })
  return { promise, resolve, reject }
}

describe('Lazy Worksheet modal', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    vi.resetModules()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    vi.doUnmock('./DeckWorksheetModal')
    vi.restoreAllMocks()
  })

  it('loads only on open, allows cancelling the pending load, and forwards the original modal props', async () => {
    const request = deferred<{ DeckWorksheetModal: ComponentType<DeckWorksheetModalProps> }>()
    const load = vi.fn(() => request.promise)
    vi.doMock('./DeckWorksheetModal', load)
    const { LazyDeckWorksheetModal } = await import('./LazyDeckWorksheetModal')
    function Host() {
      const [open, setOpen] = useState(false)
      return <>
        <button onClick={() => setOpen(true)}>Open</button>
        <LazyDeckWorksheetModal open={open} onOpenChange={setOpen} deckId={42} initialCardIds={['card-1']} />
      </>
    }
    await act(async () => root.render(<Host />))
    expect(load).not.toHaveBeenCalled()

    await act(async () => container.querySelector('button')?.click())
    expect(load).toHaveBeenCalledTimes(1)
    expect(document.querySelector('[role="status"]')).not.toBeNull()
    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    expect(document.querySelector('[role="dialog"]')).toBeNull()

    const loaded = vi.fn((props: DeckWorksheetModalProps) => <div role="dialog">Loaded {props.deckId}</div>)
    await act(async () => request.resolve({ DeckWorksheetModal: loaded }))
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    await act(async () => container.querySelector('button')?.click())
    expect(document.querySelector('[role="dialog"]')?.textContent).toBe('Loaded 42')
    expect(loaded.mock.calls[0][0]).toMatchObject({ open: true, deckId: 42, initialCardIds: ['card-1'] })
  })

  it('keeps a failed chunk load local and leaves its dialog cancellable', async () => {
    const request = deferred<never>()
    vi.doMock('./DeckWorksheetModal', () => request.promise)
    const { LazyDeckWorksheetModal } = await import('./LazyDeckWorksheetModal')
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    function Host() {
      const [open, setOpen] = useState(true)
      return <>
        <p>Existing page</p>
        <LazyDeckWorksheetModal open={open} onOpenChange={setOpen} deckId={42} />
      </>
    }
    await act(async () => root.render(<Host />))
    await act(async () => request.reject(new Error('Chunk unavailable')))
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Không thể tải công cụ')
    expect(container.textContent).toContain('Existing page')
    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })
})

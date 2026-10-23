// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDebounce, useDebouncedCallback } from './useDebounce'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('useDebounce and useDebouncedCallback', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    vi.useFakeTimers()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.useRealTimers()
  })

  describe('useDebounce', () => {
    function DebounceTestComponent({ value, delay }: { value: string; delay?: number }) {
      const debounced = useDebounce(value, delay)
      return <span id="debounced-output">{debounced}</span>
    }

    it('returns initial value immediately', async () => {
      await act(async () => {
        root.render(<DebounceTestComponent value="initial" delay={300} />)
      })

      expect(container.querySelector('#debounced-output')?.textContent).toBe('initial')
    })

    it('delays updating value until specified timeout', async () => {
      await act(async () => {
        root.render(<DebounceTestComponent value="first" delay={300} />)
      })

      expect(container.querySelector('#debounced-output')?.textContent).toBe('first')

      // Change input prop
      await act(async () => {
        root.render(<DebounceTestComponent value="second" delay={300} />)
      })

      // Fast forward 150ms -> should still be "first"
      act(() => {
        vi.advanceTimersByTime(150)
      })
      expect(container.querySelector('#debounced-output')?.textContent).toBe('first')

      // Fast forward another 200ms -> total 350ms -> should now be "second"
      act(() => {
        vi.advanceTimersByTime(200)
      })
      expect(container.querySelector('#debounced-output')?.textContent).toBe('second')
    })
  })

  describe('useDebouncedCallback', () => {
    let callbackMock: ReturnType<typeof vi.fn<(...args: any[]) => void>>

    function CallbackTestComponent({ delay }: { delay?: number }) {
      const debouncedFn = useDebouncedCallback(callbackMock, delay)
      return (
        <div>
          <button id="trigger" onClick={() => debouncedFn('arg1')}>
            Trigger
          </button>
          <button id="cancel" onClick={() => debouncedFn.cancel()}>
            Cancel
          </button>
        </div>
      )
    }

    beforeEach(() => {
      callbackMock = vi.fn()
    })

    it('only calls callback once after rapid triggers', async () => {
      await act(async () => {
        root.render(<CallbackTestComponent delay={200} />)
      })

      const btn = container.querySelector<HTMLButtonElement>('#trigger')!

      act(() => {
        btn.click()
        btn.click()
        btn.click()
      })

      expect(callbackMock).not.toHaveBeenCalled()

      act(() => {
        vi.advanceTimersByTime(250)
      })

      expect(callbackMock).toHaveBeenCalledTimes(1)
      expect(callbackMock).toHaveBeenCalledWith('arg1')
    })

    it('allows canceling pending invocation', async () => {
      await act(async () => {
        root.render(<CallbackTestComponent delay={200} />)
      })

      const triggerBtn = container.querySelector<HTMLButtonElement>('#trigger')!
      const cancelBtn = container.querySelector<HTMLButtonElement>('#cancel')!

      act(() => {
        triggerBtn.click()
      })

      act(() => {
        cancelBtn.click()
        vi.advanceTimersByTime(300)
      })

      expect(callbackMock).not.toHaveBeenCalled()
    })
  })
})

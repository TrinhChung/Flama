// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  safeLocalStorageGet,
  safeLocalStorageRemove,
  safeLocalStorageSet,
  useLocalStorage,
} from './useLocalStorage'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('useLocalStorage and safeLocalStorage utilities', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    window.localStorage.clear()
  })

  describe('standalone helpers', () => {
    it('sets and gets values correctly', () => {
      expect(safeLocalStorageSet('test_key', { count: 42 })).toBe(true)
      const res = safeLocalStorageGet('test_key', { count: 0 })
      expect(res).toEqual({ count: 42 })
    })

    it('returns fallback when item does not exist', () => {
      const res = safeLocalStorageGet('non_existent', 'fallback')
      expect(res).toBe('fallback')
    })

    it('handles JSON parse error gracefully', () => {
      window.localStorage.setItem('invalid_json', '{bad}')
      const res = safeLocalStorageGet('invalid_json', 'default')
      expect(res).toBe('default')
    })

    it('removes item correctly', () => {
      safeLocalStorageSet('key_to_delete', 'value')
      expect(safeLocalStorageRemove('key_to_delete')).toBe(true)
      expect(window.localStorage.getItem('key_to_delete')).toBeNull()
    })

    it('handles localStorage.setItem throwing safely', () => {
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('QuotaExceededError')
      })
      const success = safeLocalStorageSet('overflow', 'data')
      expect(success).toBe(false)
    })
  })

  describe('useLocalStorage hook', () => {
    function TestComponent({
      storageKey,
      initial,
    }: {
      storageKey: string
      initial: string
    }) {
      const [val, setVal, removeVal] = useLocalStorage(storageKey, initial)
      return (
        <div>
          <span id="stored-val">{val}</span>
          <button id="btn-update" onClick={() => setVal('updated_value')}>
            Update
          </button>
          <button id="btn-remove" onClick={() => removeVal()}>
            Remove
          </button>
        </div>
      )
    }

    it('initializes with initialValue when nothing is in storage', async () => {
      await act(async () => {
        root.render(<TestComponent storageKey="my_key" initial="hello" />)
      })

      expect(container.querySelector('#stored-val')?.textContent).toBe('hello')
    })

    it('initializes with stored value if present in localStorage', async () => {
      window.localStorage.setItem('existing_key', JSON.stringify('saved_hello'))

      await act(async () => {
        root.render(<TestComponent storageKey="existing_key" initial="hello" />)
      })

      expect(container.querySelector('#stored-val')?.textContent).toBe('saved_hello')
    })

    it('updates state and persists to localStorage on setVal', async () => {
      await act(async () => {
        root.render(<TestComponent storageKey="persist_key" initial="hello" />)
      })

      const updateBtn = container.querySelector<HTMLButtonElement>('#btn-update')!
      await act(async () => {
        updateBtn.click()
      })

      expect(container.querySelector('#stored-val')?.textContent).toBe('updated_value')
      expect(window.localStorage.getItem('persist_key')).toBe(JSON.stringify('updated_value'))
    })

    it('resets to initial and clears storage on removeVal', async () => {
      window.localStorage.setItem('remove_key', JSON.stringify('pre_existing'))

      await act(async () => {
        root.render(<TestComponent storageKey="remove_key" initial="initial_text" />)
      })

      expect(container.querySelector('#stored-val')?.textContent).toBe('pre_existing')

      const removeBtn = container.querySelector<HTMLButtonElement>('#btn-remove')!
      await act(async () => {
        removeBtn.click()
      })

      expect(container.querySelector('#stored-val')?.textContent).toBe('initial_text')
      expect(window.localStorage.getItem('remove_key')).toBeNull()
    })
  })
})

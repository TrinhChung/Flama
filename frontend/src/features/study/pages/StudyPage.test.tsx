// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  requestFullscreen: vi.fn(),
  requestTakeover: vi.fn(),
  answer: vi.fn(),
  commit: vi.fn(),
  prepareDecision: vi.fn(),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
    useSearchParams: () => [new URLSearchParams('deck_id=12')],
  }
})

vi.mock('../hooks/useStudySession', () => ({
  useStudySession: () => ({
    session: null,
    view: null,
    receipt: null,
    error: null,
    leaseConflict: true,
    takeoverState: 'idle',
    isLoading: false,
    isBusy: false,
    prepareDecision: mocks.prepareDecision,
    answer: mocks.answer,
    commit: mocks.commit,
    requestTakeover: mocks.requestTakeover,
  }),
}))

import { StudyPage } from './StudyPage'

let root: Root | null = null
let container: HTMLDivElement | null = null

beforeEach(() => {
  for (const mock of Object.values(mocks)) mock.mockReset()
  mocks.requestFullscreen.mockResolvedValue(undefined)
  Object.defineProperty(document.documentElement, 'requestFullscreen', {
    configurable: true,
    value: mocks.requestFullscreen,
  })
})

afterEach(async () => {
  if (root) await act(async () => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

describe('StudyPage session conflict keyboard behavior', () => {
  it('leaves Enter, Space, and fullscreen shortcuts to the conflict UI', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(<StudyPage />)
    })

    const takeoverButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Chuyển phiên sang tab này'),
    )
    expect(takeoverButton).toBeDefined()
    takeoverButton?.focus()

    for (const event of [
      new KeyboardEvent('keydown', {
        key: 'Enter',
        code: 'Enter',
        bubbles: true,
        cancelable: true,
      }),
      new KeyboardEvent('keydown', {
        key: ' ',
        code: 'Space',
        bubbles: true,
        cancelable: true,
      }),
      new KeyboardEvent('keydown', {
        key: 'f',
        code: 'KeyF',
        bubbles: true,
        cancelable: true,
      }),
    ]) {
      await act(async () => {
        window.dispatchEvent(event)
      })
      expect(event.defaultPrevented).toBe(false)
    }

    expect(mocks.prepareDecision).not.toHaveBeenCalled()
    expect(mocks.answer).not.toHaveBeenCalled()
    expect(mocks.requestFullscreen).not.toHaveBeenCalled()
  })
})

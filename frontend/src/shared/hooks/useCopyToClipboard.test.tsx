// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useCopyToClipboard } from './useCopyToClipboard'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('useCopyToClipboard', () => {
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
    vi.restoreAllMocks()
  })

  function ClipboardTestComponent({
    textToCopy,
    resetTimeout = 1000,
  }: {
    textToCopy: string
    resetTimeout?: number
  }) {
    const { copy, isCopied, copiedText } = useCopyToClipboard({ resetTimeout })
    return (
      <div>
        <button id="copy-btn" onClick={() => void copy(textToCopy)}>
          Copy
        </button>
        <span id="status">{isCopied ? 'COPIED' : 'IDLE'}</span>
        <span id="copied-text">{copiedText || 'NONE'}</span>
      </div>
    )
  }

  it('successfully copies text using navigator.clipboard', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    })

    await act(async () => {
      root.render(<ClipboardTestComponent textToCopy="Flama Note" />)
    })

    const btn = container.querySelector<HTMLButtonElement>('#copy-btn')!

    await act(async () => {
      btn.click()
    })

    expect(writeTextMock).toHaveBeenCalledWith('Flama Note')
    expect(container.querySelector('#status')?.textContent).toBe('COPIED')
    expect(container.querySelector('#copied-text')?.textContent).toBe('Flama Note')

    // Advance timer past resetTimeout (1000ms)
    act(() => {
      vi.advanceTimersByTime(1100)
    })

    expect(container.querySelector('#status')?.textContent).toBe('IDLE')
    expect(container.querySelector('#copied-text')?.textContent).toBe('NONE')
  })

  it('falls back to document.execCommand when navigator.clipboard is unavailable', async () => {
    // Delete navigator.clipboard
    // @ts-expect-error delete clipboard
    delete navigator.clipboard
    const execCommandSpy = vi.fn().mockReturnValue(true)
    document.execCommand = execCommandSpy

    await act(async () => {
      root.render(<ClipboardTestComponent textToCopy="Fallback Text" />)
    })

    const btn = container.querySelector<HTMLButtonElement>('#copy-btn')!

    await act(async () => {
      btn.click()
    })

    expect(execCommandSpy).toHaveBeenCalledWith('copy')
    expect(container.querySelector('#status')?.textContent).toBe('COPIED')
    expect(container.querySelector('#copied-text')?.textContent).toBe('Fallback Text')
  })
})

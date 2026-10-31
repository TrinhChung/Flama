// @vitest-environment jsdom

import { act, type ReactNode } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { IssuedTokenResult } from '../types'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const { writeText, success, error } = vi.hoisted(() => ({
  writeText: vi.fn(), success: vi.fn(), error: vi.fn(),
}))
vi.mock('sonner', () => ({ toast: { success, error } }))
// Keep these lifecycle checks independent of Radix's own focus/animation timers.
vi.mock('@/components/ui/dialog', () => {
  const Part = ({ children }: { children: ReactNode }) => <div>{children}</div>
  return { Dialog: ({ open, children }: { open: boolean; children: ReactNode }) => open ? <div>{children}</div> : null,
    DialogContent: Part, DialogHeader: Part, DialogTitle: Part, DialogDescription: Part, DialogFooter: Part }
})
vi.mock('@/shared/ui', () => ({ CodeSnippetBox: ({ code }: { code: string }) => <pre>{code}</pre> }))

import i18n, { i18nReady } from '@/shared/config/i18n'
import { FLAMA_MCP_URL } from '@/shared/config/env'
import { McpTokenSecretModal } from './McpTokenSecretModal'

describe('MCP secret modal clipboard lifecycle', () => {
  let root: Root | null
  let container: HTMLDivElement
  const token: IssuedTokenResult = { token: 'test-token-only', name: 'Test token' }

  beforeEach(async () => {
    await i18nReady
    await i18n.changeLanguage('vi')
    vi.useFakeTimers()
    vi.clearAllMocks()
    writeText.mockReset().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    if (root) await act(async () => root!.unmount())
    container.remove()
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  async function render(open = true, issuedToken = token) {
    await act(async () => root!.render(<McpTokenSecretModal issuedToken={issuedToken} isOpen={open} onClose={() => {}} />))
  }

  async function copy(target: 'token' | 'url' = 'token') {
    const buttons = container.querySelectorAll('button')
    await act(async () => buttons[target === 'token' ? 0 : 1].click())
  }

  async function unmount() {
    await act(async () => root!.unmount())
    root = null
  }

  it.each(['token', 'url'] as const)('cancels the %s reset timer when unmounted', async (target) => {
    await render()
    await copy(target)
    expect(writeText).toHaveBeenCalledWith(target === 'token' ? token.token
      : `${FLAMA_MCP_URL.replace(/\/+$/, '')}/${encodeURIComponent(token.token)}`)
    expect(vi.getTimerCount()).toBe(1)
    await unmount()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('clears timers and feedback when closed and reopened with the same token', async () => {
    await render()
    await copy()
    expect(container.querySelectorAll('button')[0].textContent).toContain('Đã chép')
    await render(false)
    expect(vi.getTimerCount()).toBe(0)
    await render()
    expect(container.querySelectorAll('button')[0].textContent).toContain('Sao chép')
  })

  it('does not schedule feedback when a clipboard write finishes after unmount', async () => {
    let finish!: () => void
    writeText.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
    await render()
    await copy()
    await unmount()
    await act(async () => finish())
    expect(vi.getTimerCount()).toBe(0)
    expect(success).not.toHaveBeenCalled()
  })

  it('ignores a clipboard write from a previous opening of the same token', async () => {
    let finish!: () => void
    writeText.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
    await render()
    await copy()
    await render(false)
    await render()
    await act(async () => finish())
    expect(vi.getTimerCount()).toBe(0)
    expect(success).not.toHaveBeenCalled()
    expect(container.querySelectorAll('button')[0].textContent).toContain('Sao chép')
  })

  it('clears both feedback timers when another token is issued', async () => {
    await render()
    await copy('token')
    await copy('url')
    expect(vi.getTimerCount()).toBe(2)
    await render(true, { token: 'new-test-token-only', name: 'Rotated token' })
    expect(vi.getTimerCount()).toBe(0)
    expect(container.querySelectorAll('button')[0].textContent).toContain('Sao chép')
    expect(container.querySelectorAll('button')[1].textContent).toContain('Sao chép URL')
  })

  it('restarts each feedback interval independently on repeated copies', async () => {
    await render()
    await copy('token')
    await act(async () => vi.advanceTimersByTime(500))
    await copy('url')
    await act(async () => vi.advanceTimersByTime(500))
    await copy('token')
    expect(vi.getTimerCount()).toBe(2)
    await act(async () => vi.advanceTimersByTime(1000))
    expect(container.querySelectorAll('button')[0].textContent).toContain('Đã chép')
    expect(container.querySelectorAll('button')[1].textContent).toContain('Đã chép')
    await act(async () => vi.advanceTimersByTime(500))
    expect(container.querySelectorAll('button')[0].textContent).toContain('Đã chép')
    expect(container.querySelectorAll('button')[1].textContent).toContain('Sao chép URL')
    await act(async () => vi.advanceTimersByTime(500))
    expect(container.querySelectorAll('button')[0].textContent).toContain('Sao chép')
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores a rejected clipboard promise after close', async () => {
    let fail!: (reason: Error) => void
    writeText.mockImplementationOnce(() => new Promise<void>((_resolve, reject) => { fail = reject }))
    await render()
    await copy()
    await render(false)
    await act(async () => fail(new Error('Clipboard denied after close')))
    expect(error).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FlamaAudioConnectionGate } from './FlamaAudioConnectionGate'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const client = vi.hoisted(() => ({
  getHealth: vi.fn(), getToken: vi.fn(), startPairing: vi.fn(), getPairingStatus: vi.fn(),
  setToken: vi.fn(), getVoices: vi.fn(),
}))
vi.mock('@/lib/flamaAudioClient', () => ({ flamaAudioClient: client }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))

function challenge(id: string, approved = false) {
  return { pairing_id: id, approved, token: approved ? `${id}-token` : undefined }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('audio connection pairing polling', () => {
  let container: HTMLDivElement
  let root: Root
  const onConnectionChange = vi.fn()
  const render = () => <MemoryRouter><FlamaAudioConnectionGate onConnectionChange={onConnectionChange} /></MemoryRouter>

  const click = async (text: string) => {
    const button = Array.from(container.querySelectorAll('button')).find((item) => item.textContent?.includes(text))
    expect(button).toBeDefined()
    await act(async () => { button!.click() })
  }

  beforeEach(async () => {
    vi.useFakeTimers()
    vi.resetAllMocks()
    client.getHealth.mockResolvedValue({ version: '1.0.0' })
    client.getToken.mockReturnValue(null)
    client.startPairing.mockResolvedValue(challenge('first'))
    client.getPairingStatus.mockResolvedValue(challenge('first'))
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
    await act(async () => { root.render(render()) })
  })

  afterEach(async () => {
    await act(async () => { root.unmount() })
    container.remove()
    vi.useRealTimers()
  })

  it('ends pairing after 40 unapproved responses', async () => {
    await act(async () => { await vi.advanceTimersByTimeAsync(120_000) })
    expect(client.getPairingStatus).toHaveBeenCalledTimes(40)
    expect(container.querySelector('code')?.textContent).toBe('gate.generating_challenge')
    expect(client.setToken).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cancels the previous challenge and rejects its late approval when resending', async () => {
    const pending = deferred<ReturnType<typeof challenge>>()
    client.getPairingStatus.mockReturnValueOnce(pending.promise)
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    const oldSignal = client.getPairingStatus.mock.calls[0][1] as AbortSignal
    client.startPairing.mockResolvedValue(challenge('second'))
    await click('gate.resend_request')
    expect(oldSignal.aborted).toBe(true)
    await act(async () => { pending.resolve(challenge('first', true)) })
    expect(client.setToken).not.toHaveBeenCalled()
    expect(container.querySelector('code')?.textContent).toBe('second')
    await act(async () => { await vi.advanceTimersByTimeAsync(1500) })
    expect(client.getPairingStatus).toHaveBeenLastCalledWith('second', expect.any(AbortSignal))
  })

  it('does not overlap pending pairing requests and cancels polling when unmounted', async () => {
    const pending = deferred<ReturnType<typeof challenge>>()
    client.getPairingStatus.mockReturnValue(pending.promise)
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.getPairingStatus).toHaveBeenCalledTimes(1)
    const signal = client.getPairingStatus.mock.calls[0][1] as AbortSignal
    await act(async () => { root.unmount() })
    root = createRoot(container)
    expect(signal.aborted).toBe(true)
    await act(async () => { pending.resolve(challenge('first', true)); await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.setToken).not.toHaveBeenCalled()
    expect(onConnectionChange).not.toHaveBeenCalledWith(true)
    expect(client.getPairingStatus).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('cancels the old pairing challenge when retrying the service health check', async () => {
    const signal = client.startPairing.mock.calls[0][1] as AbortSignal
    client.getToken.mockReturnValue('existing-token')
    client.getVoices.mockResolvedValue([])
    await click('gate.retry_button')
    expect(signal.aborted).toBe(true)
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(client.getPairingStatus).not.toHaveBeenCalled()
    expect(onConnectionChange).toHaveBeenLastCalledWith(true)
  })
})

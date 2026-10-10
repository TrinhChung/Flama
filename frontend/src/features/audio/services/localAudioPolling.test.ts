import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { startLocalAudioPolling } from './localAudioPolling'

describe('desktop audio polling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('exhausts its budget for successful empty responses and request failures', async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue([])
    const onExhausted = vi.fn()
    startLocalAudioPolling({
      signal: new AbortController().signal,
      intervalMs: 1500,
      maxAttempts: 3,
      request,
      onResult: (voices: unknown[]) => voices.length > 0,
      onExhausted,
    })

    await vi.advanceTimersByTimeAsync(30_000)
    expect(request).toHaveBeenCalledTimes(3)
    expect(onExhausted).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('waits for an in-flight request to settle before scheduling the next attempt', async () => {
    let resolve!: (value: boolean) => void
    const request = vi.fn().mockImplementationOnce(() => new Promise<boolean>((done) => { resolve = done }))
      .mockResolvedValue(true)
    const onResult = vi.fn((ready: boolean) => ready)
    startLocalAudioPolling({
      signal: new AbortController().signal,
      intervalMs: 1500,
      maxAttempts: 3,
      request,
      onResult,
    })

    await vi.advanceTimersByTimeAsync(30_000)
    expect(request).toHaveBeenCalledTimes(1)
    resolve(false)
    await vi.advanceTimersByTimeAsync(1499)
    expect(request).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(request).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores a late response from an aborted request without exhausting or rescheduling', async () => {
    const controller = new AbortController()
    let resolve!: (value: boolean) => void
    const request = vi.fn(() => new Promise<boolean>((done) => { resolve = done }))
    const onResult = vi.fn(() => true)
    const onExhausted = vi.fn()
    startLocalAudioPolling({ signal: controller.signal, intervalMs: 100, maxAttempts: 1, request, onResult, onExhausted })
    await vi.advanceTimersByTimeAsync(100)
    expect(request).toHaveBeenCalledWith(controller.signal)
    controller.abort()
    resolve(true)
    await vi.advanceTimersByTimeAsync(10_000)
    expect(onResult).not.toHaveBeenCalled()
    expect(onExhausted).not.toHaveBeenCalled()
    expect(request).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('never sends a request when cancelled before the first attempt', async () => {
    const controller = new AbortController()
    const request = vi.fn()
    startLocalAudioPolling({ signal: controller.signal, intervalMs: 100, maxAttempts: 1, request, onResult: () => false })
    controller.abort()
    await vi.advanceTimersByTimeAsync(10_000)
    expect(request).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})

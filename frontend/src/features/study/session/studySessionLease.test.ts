import { describe, expect, it, vi } from 'vitest'
import { holdStudyScopeLease } from './studySessionLease'

function rejectInvalidOptions(options: LockOptions) {
  if (
    (options.signal && (options.ifAvailable || options.steal))
    || (options.ifAvailable && options.steal)
  ) {
    throw new DOMException(
      "The 'signal' option cannot be combined with 'ifAvailable' or 'steal'.",
      'NotSupportedError',
    )
  }
}

describe('study session scope lease', () => {
  it('acquires a free scope with a spec-valid probe', async () => {
    const lockManager = {
      request: vi.fn((
        _name: string,
        options: LockOptions,
        callback: (lock: Lock | null) => unknown,
      ) => {
        rejectInvalidOptions(options)
        return Promise.resolve(callback({
          name: 'lease',
          mode: 'exclusive',
        } as Lock))
      }),
    } as unknown as LockManager
    const controller = new AbortController()
    const onAcquired = vi.fn()

    const lease = holdStudyScopeLease(
      lockManager,
      'flama-study:user:7:deck:12',
      controller.signal,
      { onBlocked: vi.fn(), onAcquired },
    )
    await vi.waitFor(() => expect(onAcquired).toHaveBeenCalledOnce())

    expect(lockManager.request).toHaveBeenCalledTimes(1)
    expect(lockManager.request).toHaveBeenCalledWith(
      'flama-study:user:7:deck:12',
      { mode: 'exclusive', ifAvailable: true },
      expect.any(Function),
    )

    controller.abort()
    await expect(lease).resolves.toBeUndefined()
  })

  it('waits for the previous tab and acquires the lease after it closes', async () => {
    let grantQueuedRequest: (() => void) | null = null
    const lockManager = {
      request: vi.fn((
        _name: string,
        options: LockOptions,
        callback: (lock: Lock | null) => unknown,
      ) => {
        rejectInvalidOptions(options)
        if (options.ifAvailable) {
          return Promise.resolve(callback(null))
        }
        return new Promise((resolve) => {
          grantQueuedRequest = () => {
            Promise.resolve(callback({ name: 'lease', mode: 'exclusive' } as Lock))
              .then(resolve)
          }
        })
      }),
    } as unknown as LockManager
    const controller = new AbortController()
    const states: string[] = []

    const lease = holdStudyScopeLease(
      lockManager,
      'flama-study:user:7:deck:12',
      controller.signal,
      {
        onBlocked: () => states.push('blocked'),
        onAcquired: () => states.push('acquired'),
      },
    )
    await vi.waitFor(() => expect(states).toEqual(['blocked']))

    expect(grantQueuedRequest).not.toBeNull()
    ;(grantQueuedRequest as (() => void) | null)?.()
    await vi.waitFor(() => expect(states).toEqual(['blocked', 'acquired']))

    controller.abort()
    await expect(lease).resolves.toBeUndefined()
    expect(lockManager.request).toHaveBeenCalledTimes(2)
    expect(lockManager.request).toHaveBeenNthCalledWith(
      1,
      'flama-study:user:7:deck:12',
      { mode: 'exclusive', ifAvailable: true },
      expect.any(Function),
    )
    expect(lockManager.request).toHaveBeenNthCalledWith(
      2,
      'flama-study:user:7:deck:12',
      { mode: 'exclusive', signal: controller.signal },
      expect.any(Function),
    )
  })

  it('cancels a queued request without acquiring the scope', async () => {
    const onAcquired = vi.fn()
    const onBlocked = vi.fn()
    const lockManager = {
      request: vi.fn((
        _name: string,
        options: LockOptions,
        callback: (lock: Lock | null) => unknown,
      ) => {
        rejectInvalidOptions(options)
        if (options.ifAvailable) return Promise.resolve(callback(null))
        return new Promise((_resolve, reject) => {
          options.signal?.addEventListener(
            'abort',
            () => reject(options.signal?.reason),
            { once: true },
          )
        })
      }),
    } as unknown as LockManager
    const controller = new AbortController()

    const lease = holdStudyScopeLease(
      lockManager,
      'flama-study:user:7:deck:12',
      controller.signal,
      { onBlocked, onAcquired },
    )
    await vi.waitFor(() => expect(onBlocked).toHaveBeenCalledOnce())

    controller.abort()
    await expect(lease).resolves.toBeUndefined()
    expect(onAcquired).not.toHaveBeenCalled()
  })

  it('fails closed when Web Locks is unavailable', async () => {
    const controller = new AbortController()
    const onAcquired = vi.fn()
    await expect(holdStudyScopeLease(
        undefined,
        'flama-study:user:7:deck:12',
        controller.signal,
        { onBlocked: vi.fn(), onAcquired },
      )).rejects.toThrow('HTTPS')
    expect(onAcquired).not.toHaveBeenCalled()
  })

  it('notifies the previous owner when a held lease is stolen', async () => {
    let rejectHeldRequest: ((reason: unknown) => void) | null = null
    const lockManager = {
      request: vi.fn((
        _name: string,
        options: LockOptions,
        callback: (lock: Lock | null) => unknown,
      ) => {
        rejectInvalidOptions(options)
        return new Promise((resolve, reject) => {
          rejectHeldRequest = reject
          void Promise.resolve(callback({
            name: 'lease',
            mode: 'exclusive',
          } as Lock)).then(resolve, reject)
        })
      }),
    } as unknown as LockManager
    const controller = new AbortController()
    const onAcquired = vi.fn()
    const onLost = vi.fn(() => controller.abort())

    const lease = holdStudyScopeLease(
      lockManager,
      'flama-study:user:7:deck:12',
      controller.signal,
      { onBlocked: vi.fn(), onAcquired, onLost },
    )
    await vi.waitFor(() => expect(onAcquired).toHaveBeenCalledOnce())

    expect(rejectHeldRequest).not.toBeNull()
    ;(rejectHeldRequest as ((reason: unknown) => void) | null)?.(
      new DOMException('The lock was stolen.', 'AbortError'),
    )
    await expect(lease).resolves.toBeUndefined()
    expect(onLost).toHaveBeenCalledOnce()
  })
})

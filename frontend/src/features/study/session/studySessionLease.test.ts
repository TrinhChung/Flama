import { describe, expect, it, vi } from 'vitest'
import { holdStudyScopeLease } from './studySessionLease'

describe('study session scope lease', () => {
  it('waits for the previous tab and acquires the lease after it closes', async () => {
    let grantQueuedRequest: (() => void) | null = null
    const lockManager = {
      request: vi.fn((
        _name: string,
        options: LockOptions,
        callback: (lock: Lock | null) => unknown,
      ) => {
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
  })
})

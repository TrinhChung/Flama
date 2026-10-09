// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FlamaAudioClient } from './flamaAudioClient'

describe('desktop client request cancellation', () => {
  const fetchRequest = vi.fn()
  beforeEach(() => {
    localStorage.clear()
    fetchRequest.mockReset().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchRequest)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('passes the caller signal to every cancellable connection and engine request', async () => {
    const client = new FlamaAudioClient('http://127.0.0.1:4791')
    const controller = new AbortController()
    await client.getHealth(controller.signal)
    await client.startPairing('https://flama.app', controller.signal)
    await client.getPairingStatus('challenge', controller.signal)
    await client.getVoices('voicevox', controller.signal)
    await client.installEngine('kokoro', controller.signal)
    await client.launchEngine('voicevox', controller.signal)
    expect(fetchRequest).toHaveBeenCalledTimes(6)
    for (const [, options] of fetchRequest.mock.calls) {
      expect(options.signal).toBe(controller.signal)
      expect(options.credentials).toBe('omit')
    }
  })

  it('preserves optional arguments for existing callers', async () => {
    const client = new FlamaAudioClient('http://127.0.0.1:4791')
    await client.getHealth()
    await client.getVoices()
    expect(fetchRequest).toHaveBeenLastCalledWith('http://127.0.0.1:4791/v1/voices?engine_id=voicevox', expect.objectContaining({ signal: undefined }))
  })
})

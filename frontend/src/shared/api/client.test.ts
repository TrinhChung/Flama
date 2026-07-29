// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiJsonKeepalive, setCsrfToken } from './client'

describe('apiJsonKeepalive', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    document.head.replaceChildren()
  })

  it('sends an authenticated JSON request that survives page teardown', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ success: true }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      },
    ))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-token')

    await expect(apiJsonKeepalive(
      '/api/study/sessions/session-1/commit',
      'POST',
      { events: [] },
    )).resolves.toEqual({ success: true })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        keepalive: true,
        body: JSON.stringify({ events: [] }),
        headers: expect.any(Headers),
      }),
    )
    const request = fetchMock.mock.calls[0][1] as RequestInit
    const headers = request.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('X-CSRF-Token')).toBe('csrf-token')
  })
})

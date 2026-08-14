// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  apiJson,
  apiJsonKeepalive,
  apiRequest,
  setCsrfToken,
} from './client'

describe('apiJsonKeepalive', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    setCsrfToken('')
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

  it('refreshes a stale CSRF token and retries an unsafe request once', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ error: 'CSRF_FAILED', message: 'CSRF validation failed.' }),
        {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        },
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ authenticated: true, csrf_token: 'fresh-token' }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ applied_event_count: 1 }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('stale-token')

    await expect(apiJson(
      '/api/study/sessions/session-1/commit',
      'POST',
      { commit_id: 'commit-1' },
    )).resolves.toEqual({ applied_event_count: 1 })

    expect(fetchMock).toHaveBeenCalledTimes(3)
    const firstRequest = fetchMock.mock.calls[0][1] as RequestInit
    const refreshRequest = fetchMock.mock.calls[1][1] as RequestInit
    const retriedRequest = fetchMock.mock.calls[2][1] as RequestInit
    expect((firstRequest.headers as Headers).get('X-CSRF-Token')).toBe('stale-token')
    expect(refreshRequest).toEqual(expect.objectContaining({
      method: 'GET',
      credentials: 'include',
    }))
    expect((retriedRequest.headers as Headers).get('X-CSRF-Token')).toBe('fresh-token')
    expect(retriedRequest.body).toBe(JSON.stringify({ commit_id: 'commit-1' }))
  })

  it('does not loop when the retried request still fails CSRF validation', async () => {
    const csrfFailure = () => new Response(
      JSON.stringify({ error: 'CSRF_FAILED', message: 'CSRF validation failed.' }),
      {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      },
    )
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(csrfFailure())
      .mockResolvedValueOnce(new Response(
        JSON.stringify({ authenticated: true, csrf_token: 'fresh-token' }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        },
      ))
      .mockResolvedValueOnce(csrfFailure())
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('stale-token')

    await expect(apiJson(
      '/api/study/sessions/session-1/commit',
      'POST',
      { commit_id: 'commit-1' },
    )).rejects.toMatchObject({ code: 'CSRF_FAILED', status: 400 })

    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('preserves structured error details for idempotent recovery', async () => {
    const receipt = {
      schema_version: 'study-commit-receipt.v1',
      success: true,
      session_id: 'session-1',
      commit_id: 'commit-1',
      updated_cards: [],
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({
        error: 'SESSION_ALREADY_COMMITTED',
        message: 'Study session was already committed.',
        details: receipt,
      }),
      {
        status: 409,
        headers: { 'Content-Type': 'application/json' },
      },
    )))

    const request = apiJson(
      '/api/study/sessions/session-1/commit',
      'POST',
      { commit_id: 'commit-2' },
    )
    await expect(request).rejects.toBeInstanceOf(ApiError)
    await expect(request).rejects.toMatchObject({
      code: 'SESSION_ALREADY_COMMITTED',
      details: receipt,
    })
  })

  it('preserves binary package headers and authenticates with the web session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ accepted: true }),
      {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      },
    ))
    vi.stubGlobal('fetch', fetchMock)
    setCsrfToken('csrf-token')
    const body = new Blob(['package'], { type: 'application/zip' })

    await apiRequest('/api/flashcards/import/anki/sessions/test/packages/media/0', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/zip',
        'X-Package-SHA256': 'a'.repeat(64),
      },
      body,
    })

    const request = fetchMock.mock.calls[0][1] as RequestInit
    const headers = request.headers as Headers
    expect(request.credentials).toBe('include')
    expect(headers.get('Content-Type')).toBe('application/zip')
    expect(headers.get('X-Package-SHA256')).toBe('a'.repeat(64))
    expect(headers.get('X-CSRF-Token')).toBe('csrf-token')
    expect(headers.has('Authorization')).toBe(false)
  })
})

// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from 'vitest'
import { appApi } from '@/app/api'
import { dashboardApi } from './api/dashboardApi'
import { apiRequest, setCsrfToken } from '@/shared/api/client'

function mockJson(payload: unknown) {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(
    JSON.stringify(payload), { headers: { 'Content-Type': 'application/json' } },
  )))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function mockTimezone(timeZone: string) {
  const resolved = Intl.DateTimeFormat().resolvedOptions()
  vi.spyOn(Intl.DateTimeFormat.prototype, 'resolvedOptions').mockReturnValue({ ...resolved, timeZone })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  setCsrfToken('')
})

describe('Dashboard transport regression coverage', () => {
  it('loads session without an automatic timezone header or custom fetch option', async () => {
    const fetchMock = mockJson({ authenticated: false, user: null, csrf_token: 'csrf' })
    const bootstrap = await appApi.getBootstrap()
    expect(bootstrap.csrf_token).toBe('csrf')
    const init = fetchMock.mock.calls[0][1]
    expect(init.headers.has('X-Timezone')).toBe(false)
    expect(init.credentials).toBe('include')
    expect(init).not.toHaveProperty('includeTimezone')
  })

  it('maps compact nested decks while preserving copy aliases, URLs and counts', async () => {
    const child = {
      deck_id: 11, parent_id: 10, move_alias: 'MID-CHILD', label: 'Child', depth: 1,
      new_count: 2, learn_count: 1, due_count: 3, note_type_id: null, children: [],
    }
    const fetchMock = mockJson({
      items: [{ ...child, deck_id: 10, parent_id: null, move_alias: 'MID-ROOT', label: 'Root', depth: 0, children: [child] }],
      summary: { new: 2, learning: 1, due: 3, total_due: 6 },
      admin_mode: true,
    })
    const result = await dashboardApi.getDashboard()
    expect(fetchMock.mock.calls[0][0]).toContain('/dashboard?compact=1')
    expect(fetchMock.mock.calls[0][1].headers.has('X-Timezone')).toBe(false)
    expect(result.decks[0].children[0]).toMatchObject({
      id: 11, parent_id: 10, study_url: '/study?deck_id=11',
      counts: { new: 2, learning: 1, due: 3 },
      move: { alias: 'MID-CHILD', token: '', parent_alias: null, parent_token: null },
    })
    expect(result.decks[0].move.alias).toBe('MID-ROOT')
  })

  it('sends the browser timezone in the overview query, preserving year and credentials', async () => {
    mockTimezone('America/New_York')
    const fetchMock = mockJson({ days: [] })
    await appApi.getDashboardOverview(2025)
    const url = new URL(fetchMock.mock.calls[0][0], 'http://localhost')
    expect(url.searchParams.get('year')).toBe('2025')
    expect(url.searchParams.get('timezone')).toBe('America/New_York')
    expect(fetchMock.mock.calls[0][1].headers.has('X-Timezone')).toBe(false)
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
  })

  it('retains timezone headers for other GET APIs that read them', async () => {
    mockTimezone('Europe/Paris')
    const fetchMock = mockJson({ ok: true })
    await apiRequest('/api/statistics/today-future?scope=collection')
    expect(fetchMock.mock.calls[0][1].headers.get('X-Timezone')).toBe('Europe/Paris')
  })

  it('preserves an explicit timezone even when automatic headers are disabled', async () => {
    const fetchMock = mockJson({ ok: true })
    await apiRequest('/api/statistics/overview', {
      includeTimezone: false, headers: { 'X-Timezone': 'Asia/Seoul' },
    })
    expect(fetchMock.mock.calls[0][1].headers.get('X-Timezone')).toBe('Asia/Seoul')
  })

  it('uses the stored server timezone if browser timezone lookup fails', async () => {
    const fetchMock = mockJson({ days: [] })
    vi.spyOn(Intl, 'DateTimeFormat').mockImplementation(() => { throw new Error('Intl unavailable') })
    await expect(appApi.getDashboardOverview(2026)).resolves.toEqual({ days: [] })
    const url = new URL(fetchMock.mock.calls[0][0], 'http://localhost')
    expect(url.searchParams.has('timezone')).toBe(false)
  })
})

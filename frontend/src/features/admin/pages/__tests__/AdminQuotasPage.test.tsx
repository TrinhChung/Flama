// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminQuotasPage } from '../AdminQuotasPage'
import type { QuotaOverview, QuotaUserDetail } from '../../types/quotas'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver

const mocks = vi.hoisted(() => ({
  apiRequest: vi.fn(),
  apiJson: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('@/shared/api/client', () => ({
  apiRequest: mocks.apiRequest,
  apiJson: mocks.apiJson,
}))

vi.mock('sonner', () => ({
  toast: { success: mocks.toastSuccess, error: mocks.toastError },
}))

function setNativeInputValue(element: HTMLInputElement, value: string) {
  const prototypeSetter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')?.set
  prototypeSetter?.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}

function clickRadix(trigger: Element) {
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) {
    trigger.dispatchEvent(new MouseEvent(type, { bubbles: true }))
  }
  ;(trigger as HTMLElement).click()
}

async function waitFor<T>(read: () => T | null | undefined): Promise<T> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    const value = read()
    if (value) return value
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10))
    })
  }
  throw new Error('Timed out waiting for the page')
}

function buttonByText(text: string, scope: ParentNode = document): HTMLButtonElement {
  const button = Array.from(scope.querySelectorAll('button')).find((node) => node.textContent?.includes(text))
  if (!button) throw new Error(`Button not found: ${text}`)
  return button as HTMLButtonElement
}

const ROLES = [
  { id: 1, code: 'regular', name: 'Học viên', user_count: 12 },
  { id: 2, code: 'creator', name: 'Creator', user_count: 3 },
  { id: 3, code: 'enterprise', name: 'Doanh nghiệp', user_count: 0 },
]

const MEMBER = { id: 7, username: 'member', email: 'member@example.com', role_name: 'Học viên', role_code: 'regular' }

function policy(kind: 'api' | 'mcp' | 'media') {
  return {
    kind,
    unit: kind === 'media' ? ('MB' as const) : ('requests' as const),
    enforce: false,
    period: 'day' as const,
    role_limits: kind === 'media' ? { regular: 100, creator: 500, enterprise: 2000 } : { regular: 300, creator: 2000, enterprise: 10000 },
    is_default: false,
    updated_at: null,
    updated_by_user_id: null,
  }
}

function usage(total: number) {
  return { period: 'day' as const, period_token: '2026-10-25', reset_epoch: 1, total, top: [], over: [] }
}

const OVERVIEW: QuotaOverview = {
  settings: { metering_enabled: true, backend: 'redis', timezone: 'Asia/Ho_Chi_Minh', cache_ttl_seconds: 30, stats_period: 'day' },
  roles: ROLES,
  policies: [policy('api'), policy('mcp'), policy('media')],
  usage: {
    api: usage(0),
    mcp: {
      ...usage(42),
      top: [{ user: MEMBER, used: 42, effective: { limit_value: 300, period: 'day', enforce: false, source: 'role', expires_on: null } }],
    },
    media: usage(0),
  },
  overrides: [
    {
      user_id: 7,
      kind: 'api',
      unit: 'requests',
      limit_value: 5000,
      period: null,
      effective_period: 'day',
      expires_at: '2026-12-31T17:00:00',
      expires_on: '2026-12-31',
      is_active: true,
      note: 'Lớp thử',
      updated_by_user_id: 1,
      updated_at: null,
      used: 12,
      user: MEMBER,
    },
  ],
}

const DETAIL: QuotaUserDetail = {
  user: MEMBER,
  quotas: (['api', 'mcp', 'media'] as const).map((kind) => ({
    kind,
    unit: kind === 'media' ? 'MB' : 'requests',
    effective: { limit_value: kind === 'api' ? 5000 : 300, period: 'day', enforce: false, source: kind === 'api' ? 'override' : 'role', expires_on: kind === 'api' ? '2026-12-31' : null },
    role_limit: 300,
    override: kind === 'api' ? OVERVIEW.overrides[0] : null,
    usage: { day: 12, month: 40, year: 90 },
  })),
}

describe('AdminQuotasPage', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    vi.clearAllMocks()
    mocks.apiRequest.mockImplementation((url: string) =>
      Promise.resolve(url.startsWith('/api/admin/quotas/users/7') ? DETAIL : OVERVIEW),
    )
    mocks.apiJson.mockImplementation((url: string) =>
      Promise.resolve(url.includes('/policies/') ? { policy: policy('api'), message: 'Đã lưu chính sách quota.' } : { ...DETAIL, message: 'ok' }),
    )
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  async function renderPage() {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await act(async () => {
      root.render(
        <QueryClientProvider client={client}>
          <AdminQuotasPage />
        </QueryClientProvider>,
      )
    })
    await waitFor(() => container.querySelector('[data-testid="quota-policy-api"]'))
  }

  it('starts every quota kind in monitor mode', async () => {
    await renderPage()
    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/admin/quotas?period=day')
    for (const kind of ['api', 'mcp', 'media']) {
      const card = container.querySelector(`[data-testid="quota-policy-${kind}"]`)
      expect(card?.textContent).toContain('Chỉ theo dõi')
    }
    expect(container.textContent).toContain('Chỉ theo dõi')
    expect(container.textContent).toContain('Học thẻ và mọi thao tác trên web không bị tính quota')
  })

  it('saves enforcement, period and role limits for one policy', async () => {
    await renderPage()
    const card = container.querySelector('[data-testid="quota-policy-api"]') as HTMLElement
    const saveButton = buttonByText('Lưu chính sách', card)
    expect(saveButton.disabled).toBe(true)

    await act(async () => clickRadix(card.querySelector('[role="switch"]')!))
    const regularInput = card.querySelector('#quota-limit-api-regular') as HTMLInputElement
    await act(async () => setNativeInputValue(regularInput, '500'))
    const enterpriseUnlimited = card.querySelector('[aria-label="Doanh nghiệp không giới hạn"]')!
    await act(async () => clickRadix(enterpriseUnlimited))
    const periodSelect = card.querySelector('#quota-period-api') as HTMLSelectElement
    await act(async () => {
      periodSelect.value = 'month'
      periodSelect.dispatchEvent(new Event('change', { bubbles: true }))
    })

    expect(saveButton.disabled).toBe(false)
    await act(async () => saveButton.click())
    expect(mocks.apiJson).toHaveBeenCalledWith('/api/admin/quotas/policies/api', 'PUT', {
      enforce: true,
      period: 'month',
      role_limits: { regular: 500, creator: 2000, enterprise: -1 },
    })
    expect(mocks.toastSuccess).toHaveBeenCalled()
  })

  it('edits a user override from the overrides tab', async () => {
    await renderPage()
    const overridesTab = Array.from(container.querySelectorAll('[role="tab"]')).find((tab) =>
      tab.textContent?.includes('Quota riêng'),
    )!
    await act(async () => clickRadix(overridesTab))
    expect(container.textContent).toContain('5.000 request / ngày')
    expect(container.textContent).toContain('31/12/2026')

    await act(async () => buttonByText('Sửa', container).click())
    const limitInput = await waitFor(() => document.querySelector<HTMLInputElement>('#override-limit-api'))
    expect(mocks.apiRequest).toHaveBeenCalledWith('/api/admin/quotas/users/7')
    expect(limitInput.value).toBe('5000')
    await act(async () => setNativeInputValue(limitInput, '8000'))
    const noteInput = document.querySelector('#override-note-api') as HTMLInputElement
    await act(async () => setNativeInputValue(noteInput, 'Gia hạn'))
    await act(async () => buttonByText('Cập nhật quota riêng').click())

    expect(mocks.apiJson).toHaveBeenCalledWith('/api/admin/quotas/users/7/api', 'PUT', {
      limit_value: 8000,
      period: null,
      expires_on: '2026-12-31',
      note: 'Gia hạn',
    })
  })
})

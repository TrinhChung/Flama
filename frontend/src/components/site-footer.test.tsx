// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SiteFooter } from './site-footer'
import type { FrontendBootstrap } from '@/shared/types/api'

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: {
      user: { id: 1, is_admin: true },
      links: { dashboard: '/dashboard' },
    },
    isPending: false,
  }),
}))

describe('SiteFooter Component (Editorial Fashion Style)', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  const mockBootstrap: FrontendBootstrap = {
    user: {
      id: 1,
      username: 'testuser',
      account_name: 'Test User',
      is_admin: true,
      role: 'admin',
      roles: ['admin'],
      permissions: [],
    },
    links: {
      dashboard: '/dashboard',
      study: '/study',
      note_types: '/note-types',
      shared_decks: '/marketplace/decks',
      shared_note_types: '/marketplace/note-types',
      terms: '/terms',
      privacy: '/privacy',
      cookies: '/cookies',
      support: '/support',
      admin_users: '/admin/users',
    },
    support_contact_email: 'support@flama.local',
    messages: [],
  } as unknown as FrontendBootstrap

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    if (root && container) {
      const activeRoot = root
      act(() => {
        activeRoot.unmount()
      })
      container.remove()
    }
    container = null
    root = null
  })

  it('renders brand, column titles, and links in balanced editorial matrix', () => {
    act(() => {
      root?.render(
        <MemoryRouter>
          <SiteFooter bootstrap={mockBootstrap} />
        </MemoryRouter>,
      )
    })

    expect(container?.textContent).toContain('Flama')
    expect(container?.textContent).toContain('Spaced Repetition')
    expect(container?.textContent).toContain('Yomitan')
    expect(container?.textContent).toContain('Anki')
    expect(container?.textContent).toContain('Học tập & Quản lý')
    expect(container?.textContent).toContain('Chợ bộ thẻ & Đóng góp')
    expect(container?.textContent).toContain('Công cụ & Tích hợp')
    expect(container?.textContent).toContain('Pháp lý & Hỗ trợ')
    expect(container?.textContent).toContain('support@flama.local')
    expect(container?.textContent).toContain('Phản hồi trong 24–48h')
    expect(container?.textContent).toContain('Lên đầu trang')
    expect(container?.textContent).toContain('Chung Trịnh')
  })

  it('renders direct concierge contact email', () => {
    act(() => {
      root?.render(
        <MemoryRouter>
          <SiteFooter bootstrap={mockBootstrap} />
        </MemoryRouter>,
      )
    })

    const mailLink = container?.querySelector('a[href="mailto:support@flama.local"]')
    expect(mailLink).not.toBeNull()
    expect(mailLink?.textContent).toContain('support@flama.local')
  })

  it('calls window.scrollTo when editorial Back to Top button is clicked', () => {
    const scrollToMock = vi.fn()
    window.scrollTo = scrollToMock

    act(() => {
      root?.render(
        <MemoryRouter>
          <SiteFooter bootstrap={mockBootstrap} />
        </MemoryRouter>,
      )
    })

    const backToTopBtn = Array.from(container?.querySelectorAll('button') || []).find((btn) =>
      btn.textContent?.includes('Lên đầu trang'),
    )
    expect(backToTopBtn).toBeDefined()

    act(() => {
      backToTopBtn?.click()
    })

    expect(scrollToMock).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' })
  })
})


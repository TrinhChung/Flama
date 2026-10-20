// @vitest-environment jsdom

// @ts-expect-error global declaration
globalThis.IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LandingStoryPreviewPage } from './LandingStoryPreviewPage'

const bootstrapState: { user: { id: number } | null } = { user: null }

vi.mock('@/shared/api/bootstrap', () => ({
  useBootstrap: () => ({
    data: { user: bootstrapState.user, links: { dashboard: '/dashboard' } },
    isPending: false,
  }),
}))

function mockMedia({ wide, reduced }: { wide: boolean; reduced: boolean }) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('prefers-reduced-motion') ? reduced : wide,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

describe('LandingStoryPreviewPage', () => {
  let container: HTMLDivElement
  let root: Root

  const render = () =>
    act(() => {
      root.render(
        <MemoryRouter initialEntries={['/landing-story-preview']}>
          <LandingStoryPreviewPage />
        </MemoryRouter>,
      )
    })

  const link = (name: string) =>
    Array.from(container.querySelectorAll('a')).find((anchor) => anchor.textContent?.trim() === name)

  const button = (name: string) =>
    Array.from(container.querySelectorAll('button')).find((element) => element.textContent?.includes(name))

  beforeEach(() => {
    bootstrapState.user = null
    window.localStorage.clear()
    mockMedia({ wide: true, reduced: false })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('tells the whole story as real headings with the community anchor', () => {
    render()

    expect(container.querySelector('h1')?.textContent).toBe('Một khám phá có thể bắt đầu từ một người.')
    expect(container.querySelectorAll('main section[aria-labelledby]')).toHaveLength(10)
    const community = container.querySelector<HTMLElement>('#flama-community')
    expect(community?.tabIndex).toBe(-1)
    expect(link('Đến với Flama')?.getAttribute('href')).toBe('#flama-community')
  })

  it('invites guests to register and log in', () => {
    render()

    expect(link('Cùng truyền lửa')?.getAttribute('href')).toBe('/register')
    expect(link('Khám phá cách Flama kết nối tri thức')?.getAttribute('href')).toBe('#flama-community')
    expect(link('Đăng nhập')?.getAttribute('href')).toBe('/login')
  })

  it('lets signed-in viewers continue without redirecting them away', () => {
    bootstrapState.user = { id: 7 }
    render()

    expect(container.querySelector('h1')).not.toBeNull()
    expect(link('Tiếp tục hành trình')?.getAttribute('href')).toBe('/dashboard')
    expect(link('Khám phá bộ thẻ cộng đồng')?.getAttribute('href')).toBe('/marketplace/decks')
    expect(link('Cùng truyền lửa')).toBeUndefined()
  })

  it('pins one stage on wide screens and switches to static keyframes when motion is turned off', () => {
    render()

    const story = container.querySelector<HTMLElement>('.story-root')
    expect(story?.dataset.mode).toBe('pinned')
    expect(container.querySelectorAll('.story-stage')).toHaveLength(1)

    act(() => button('Tắt chuyển động')?.click())

    expect(story?.dataset.mode).toBe('static')
    expect(container.querySelectorAll('.story-stage')).toHaveLength(0)
    expect(container.querySelectorAll('[data-story-art]')).toHaveLength(9)
    expect(button('Bật chuyển động')).toBeDefined()
    expect(window.localStorage.getItem('flama:landing-story:motion')).toBe('off')
  })

  it('starts in static mode when the system asks for reduced motion', () => {
    mockMedia({ wide: true, reduced: true })
    render()

    expect(container.querySelector<HTMLElement>('.story-root')?.dataset.mode).toBe('static')
  })

  it('flows chapters with their own art on small screens', () => {
    mockMedia({ wide: false, reduced: false })
    render()

    expect(container.querySelector<HTMLElement>('.story-root')?.dataset.mode).toBe('flow')
    expect(container.querySelectorAll('.story-stage')).toHaveLength(0)
    expect(container.querySelectorAll('[data-story-art]')).toHaveLength(9)
  })

  it('keeps the preview out of search results and restores the head on exit', () => {
    document.title = 'Flama'
    render()

    expect(document.querySelector('meta[name="robots"]')?.getAttribute('content')).toBe('noindex, nofollow')
    expect(document.title).toContain('bản xem trước')

    act(() => root.unmount())
    root = createRoot(container)

    expect(document.querySelector('meta[name="robots"]')).toBeNull()
    expect(document.title).toBe('Flama')
  })
})

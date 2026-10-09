// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/shared/config/i18n'
import { ContextHelpButton } from './components/ContextHelpButton'
import { GuideBreadcrumb } from './components/GuideBreadcrumb'
import { YomitanMarkersExplorer } from './components/YomitanMarkersExplorer'
import { McpToolsExplorer } from './components/McpToolsExplorer'
import type { GuideCategory } from './types'

const mockCategory: GuideCategory = {
  slug: 'general',
  title: 'Tổng quan',
  description: 'Hướng dẫn tổng quan',
  iconName: 'book',
  articles: [],
}

describe('Guide Feature Localization & Components', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(async () => {
    await i18n.changeLanguage('vi')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await i18n.changeLanguage('vi')
    act(() => root.unmount())
    container.remove()
  })

  it('renders ContextHelpButton with localized label and icon tooltip in Vietnamese and English', async () => {
    // Test default button variant (renders label)
    await act(async () => {
      root.render(
        <MemoryRouter>
          <ContextHelpButton guidePath="/guide/test" />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Trợ giúp')

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Help')

    // Test icon variant (renders aria-label on link)
    await act(async () => {
      root.render(
        <MemoryRouter>
          <ContextHelpButton guidePath="/guide/test" variant="icon" />
        </MemoryRouter>,
      )
    })

    expect(container.querySelector('a')?.getAttribute('aria-label')).toBe('View Documentation')

    await act(async () => {
      await i18n.changeLanguage('vi')
    })

    expect(container.querySelector('a')?.getAttribute('aria-label')).toBe('Xem tài liệu hướng dẫn')
  })

  it('renders GuideBreadcrumb with localized Home link', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <GuideBreadcrumb category={mockCategory} />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Trang chủ hướng dẫn')

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Guide Home')
  })

  it('renders YomitanMarkersExplorer with localized titles and filters', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <YomitanMarkersExplorer />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Khám Phá Các Marker Định Dạng Của Yomitan')
    expect(container.textContent).toContain('Tất cả marker')

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Explore Yomitan Format Markers')
    expect(container.textContent).toContain('All markers')
  })

  it('renders McpToolsExplorer with localized titles and sample prompt', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <McpToolsExplorer />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Danh Mục Công Cụ Flama MCP (19 Tools)')
    expect(container.textContent).toContain('Mẫu Prompt gợi ý')

    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Flama MCP Tools Catalog (19 Tools)')
    expect(container.textContent).toContain('Sample Prompt')
  })
})

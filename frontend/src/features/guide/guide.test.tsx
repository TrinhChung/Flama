// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import i18n from '@/shared/config/i18n'
import { ContextHelpButton } from './components/ContextHelpButton'
import { GuideBreadcrumb } from './components/GuideBreadcrumb'
import { GuideArticleRenderer } from './components/GuideArticleRenderer'
import { YomitanMarkersExplorer } from './components/YomitanMarkersExplorer'
import { McpToolsExplorer } from './components/McpToolsExplorer'
import { getArticleBySlug } from './guideData'
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

  it('resolves asbplayer guide article and renders AsbplayerInteractiveGuide with bilingual support', async () => {
    const resolved = getArticleBySlug('integrations', 'asbplayer')
    expect(resolved).toBeDefined()
    if (!resolved?.article) throw new Error('asbplayer article not found')

    const { article, category } = resolved

    expect(article.slug).toBe('asbplayer')
    expect(article.steps?.length).toBe(6)
    expect(article.shortcuts?.length).toBe(3)
    expect(article.params?.length).toBe(7)
    expect(article.troubleshoot?.length).toBe(2)

    await act(async () => {
      root.render(
        <MemoryRouter>
          <GuideArticleRenderer article={article} category={category} />
        </MemoryRouter>,
      )
    })

    // In Vietnamese
    expect(container.textContent).toContain('asbplayer')
    expect(container.textContent).toContain('6 Bước Thiết Lập')
    expect(container.textContent).toContain('Bảng Ánh Xạ Trường')
    expect(container.textContent).toContain('Mô Phỏng Thẻ Mẫu')
    expect(container.textContent).toContain('Ctrl + Shift + X')
    expect(container.textContent).toContain('http://localhost:4790/v1/anki-connect')

    // In English
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('6-Step Workflow')
    expect(container.textContent).toContain('Field Mapping Matrix')
    expect(container.textContent).toContain('Card Simulator')
    expect(container.textContent).toContain('Automated Subtitle Mining')
    expect(container.textContent).toContain('Zero Desktop Anki Required')
    expect(container.textContent).toContain('Yomitan Popup Synergy')
  })
})


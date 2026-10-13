// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { YomitanValueIntro } from '../yomitan/YomitanValueIntro'
import { AsbplayerValueIntro } from '../asbplayer/AsbplayerValueIntro'
import { McpValueIntro } from '../mcp/McpValueIntro'
import { AsbplayerFeatureHighlights } from '../asbplayer/AsbplayerFeatureHighlights'
import { YomitanFeatureHighlights } from '../yomitan/YomitanFeatureHighlights'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('Adversarial Runtime Stress Testing: Extension Value Components', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(async () => {
    localStorage.clear()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
    await act(async () => {
      await i18n.changeLanguage('vi')
    })
  })

  afterEach(async () => {
    await act(async () => {
      root.unmount()
      await i18n.changeLanguage('vi')
    })
    host.remove()
    localStorage.clear()
  })

  it('YomitanValueIntro: dynamically re-renders between Vietnamese and English without missing keys or layout crash', async () => {
    const onStartSetup = vi.fn()
    await act(async () => {
      root.render(<YomitanValueIntro onStartSetup={onStartSetup} />)
    })

    // 1. Initial Vietnamese assertions
    expect(host.textContent).toContain('Bậc thầy đọc hiểu')
    expect(host.textContent).toContain('Tại sao bạn nên kết hợp Yomitan cùng Flama?')
    expect(host.textContent).toContain('Cách học truyền thống')
    expect(host.textContent).toContain('Khi kết hợp cùng Flama')
    expect(host.textContent).toContain('Sẵn sàng kết nối tiện ích Yomitan với Flama?')
    expect(host.textContent).toContain('Đi đến Cài đặt & Tạo Token kết nối')
    expect(host.textContent).not.toContain('yomitan.tabs.overview.cta_question')
    expect(host.textContent).not.toContain('yomitan.value_intro.')

    // 2. Switch to English dynamically
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    // English assertions
    expect(host.textContent).toContain('Reading Master')
    expect(host.textContent).toContain('Why combine Yomitan with Flama?')
    expect(host.textContent).toContain('Traditional Workflow')
    expect(host.textContent).toContain('With Flama Integration')
    expect(host.textContent).toContain('Ready to connect the Yomitan extension with Flama?')
    expect(host.textContent).toContain('Proceed to Token Setup & Management')
    expect(host.textContent).not.toContain('yomitan.tabs.overview.cta_question')
    expect(host.textContent).not.toContain('yomitan.value_intro.')

    // Verify button interaction in English
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Proceed to Token Setup & Management'),
    )
    expect(ctaBtn).toBeDefined()
    act(() => {
      ctaBtn?.click()
    })
    expect(onStartSetup).toHaveBeenCalledTimes(1)

    // 3. Switch back to Vietnamese dynamically
    await act(async () => {
      await i18n.changeLanguage('vi')
    })

    expect(host.textContent).toContain('Bậc thầy đọc hiểu')
    expect(host.textContent).toContain('Tại sao bạn nên kết hợp Yomitan cùng Flama?')
    expect(host.textContent).toContain('Sẵn sàng kết nối tiện ích Yomitan với Flama?')
  })

  it('AsbplayerValueIntro: dynamically re-renders between Vietnamese and English without missing keys or layout crash', async () => {
    const onStartSetup = vi.fn()
    await act(async () => {
      root.render(<AsbplayerValueIntro onStartSetup={onStartSetup} />)
    })

    // 1. Vietnamese assertions
    expect(host.textContent).toContain('Cao thủ luyện nghe')
    expect(host.textContent).toContain('Tại sao nên kết hợp asbplayer cùng Flama?')
    expect(host.textContent).toContain('Xem phim truyền thống')
    expect(host.textContent).toContain('Khi kết hợp cùng Flama')
    expect(host.textContent).toContain('Sẵn sàng kết nối tiện ích asbplayer để khai thác phim & anime?')
    expect(host.textContent).toContain('Đi đến Cài đặt & Tạo Token kết nối')
    expect(host.textContent).not.toContain('asbplayer.tabs.overview.cta_question')
    expect(host.textContent).not.toContain('asbplayer.value_intro.')

    // 2. Switch to English dynamically
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(host.textContent).toContain('Listening Master')
    expect(host.textContent).toContain('Why combine asbplayer with Flama?')
    expect(host.textContent).toContain('Traditional Video Watching')
    expect(host.textContent).toContain('With Flama Integration')
    expect(host.textContent).toContain('Ready to connect the asbplayer extension to mine movies & anime?')
    expect(host.textContent).toContain('Proceed to Token Setup & Management')
    expect(host.textContent).not.toContain('asbplayer.tabs.overview.cta_question')
    expect(host.textContent).not.toContain('asbplayer.value_intro.')

    // Verify interaction in English
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Proceed to Token Setup & Management'),
    )
    expect(ctaBtn).toBeDefined()
    act(() => {
      ctaBtn?.click()
    })
    expect(onStartSetup).toHaveBeenCalledTimes(1)

    // 3. Switch back to Vietnamese dynamically
    await act(async () => {
      await i18n.changeLanguage('vi')
    })

    expect(host.textContent).toContain('Cao thủ luyện nghe')
    expect(host.textContent).toContain('Sẵn sàng kết nối tiện ích asbplayer để khai thác phim & anime?')
  })

  it('McpValueIntro: dynamically re-renders between Vietnamese and English without missing keys or layout crash', async () => {
    await act(async () => {
      root.render(<McpValueIntro />)
    })

    // 1. Vietnamese assertions
    expect(host.textContent).toContain('Gia sư AI riêng cho Flama')
    expect(host.textContent).toContain('Tại sao nên kết nối Trợ lý AI cùng Flama?')
    expect(host.textContent).toContain('Chat AI thông thường')
    expect(host.textContent).toContain('Khi kết nối cùng Flama (MCP)')
    expect(host.textContent).not.toContain('page.value_intro.')

    // 2. Switch to English dynamically
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(host.textContent).toContain('Personal AI Tutor for Flama')
    expect(host.textContent).toContain('Why connect AI Assistants with Flama?')
    expect(host.textContent).toContain('Regular AI Chat')
    expect(host.textContent).toContain('With Flama MCP Connection')
    expect(host.textContent).toContain('Collapse intro')
    expect(host.textContent).not.toContain('page.value_intro.')

    // 3. Switch back to Vietnamese dynamically
    await act(async () => {
      await i18n.changeLanguage('vi')
    })

    expect(host.textContent).toContain('Gia sư AI riêng cho Flama')
    expect(host.textContent).toContain('Thu gọn giới thiệu')
  })

  it('FeatureHighlights: renders domain-relevant icons and localized labels in both languages', async () => {
    await act(async () => {
      root.render(
        <div>
          <YomitanFeatureHighlights />
          <AsbplayerFeatureHighlights />
        </div>,
      )
    })

    // Vietnamese highlights check
    expect(host.textContent).toContain('Tra từ 0.1s')
    expect(host.textContent).toContain('Tạo thẻ 1-Click')
    expect(host.textContent).toContain('Video & Anime Mining')
    expect(host.textContent).toContain('Audio & Ảnh 1-Click')

    // Switch to English
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(host.textContent).toContain('0.1s Lookup')
    expect(host.textContent).toContain('1-Click Card')
    expect(host.textContent).toContain('Video & Anime Mining')
    expect(host.textContent).toContain('1-Click Audio & Image')
  })

  it('Stress edge case: handles absence of onStartSetup and disabled toggle smoothly', async () => {
    await act(async () => {
      root.render(
        <div>
          <YomitanValueIntro showToggle={false} />
          <AsbplayerValueIntro showToggle={false} />
        </div>,
      )
    })

    // No toggle button should be present
    expect(host.textContent).not.toContain('Thu gọn giới thiệu')
    expect(host.textContent).not.toContain('Tìm hiểu cách hoạt động')

    // No CTA buttons rendered when onStartSetup is omitted
    expect(host.textContent).not.toContain('Sẵn sàng kết nối tiện ích')
    expect(host.textContent).not.toContain('Đi đến Cài đặt & Tạo Token kết nối')
  })

  it('Stress edge case: handles localStorage exceptions without crashing', async () => {
    const getItemSpy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Access denied (SecurityError)')
    })
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError')
    })

    expect(() => {
      act(() => {
        root.render(<YomitanValueIntro onStartSetup={() => {}} />)
      })
    }).not.toThrow()

    // Test toggle click under storage failure
    const toggleBtn = host.querySelector('button')!
    expect(() => {
      act(() => {
        toggleBtn.click()
      })
    }).not.toThrow()

    getItemSpy.mockRestore()
    setItemSpy.mockRestore()
  })
})

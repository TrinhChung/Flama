// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import '@/shared/config/i18n'
import { YomitanValueIntro } from '../yomitan/YomitanValueIntro'
import { AsbplayerValueIntro } from '../asbplayer/AsbplayerValueIntro'
import { McpValueIntro } from '../mcp/McpValueIntro'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('Extension Value Proposition Intro Components', () => {
  let host: HTMLDivElement
  let root: Root

  beforeEach(() => {
    localStorage.clear()
    host = document.createElement('div')
    document.body.appendChild(host)
    root = createRoot(host)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    host.remove()
  })

  it('renders YomitanValueIntro, supports onStartSetup callback, and toggles collapse state', () => {
    const onStartSetup = vi.fn()
    act(() => {
      root.render(<YomitanValueIntro onStartSetup={onStartSetup} />)
    })

    // Title & badge
    expect(host.textContent).toContain('Bậc thầy đọc hiểu')
    expect(host.textContent).toContain('Tại sao bạn nên kết hợp Yomitan cùng Flama?')
    expect(host.textContent).toContain('Cách học truyền thống')
    expect(host.textContent).toContain('Khi kết hợp cùng Flama')
    expect(host.textContent).toContain('Rê chuột là thấy ngay Hiragana')

    // CTA button calling onStartSetup
    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đi đến Cài đặt & Tạo Token kết nối'),
    )
    expect(ctaBtn).toBeDefined()
    act(() => {
      ctaBtn?.click()
    })
    expect(onStartSetup).toHaveBeenCalledTimes(1)

    // Click toggle button to collapse
    const button = host.querySelector('button')!
    expect(button.textContent).toContain('Thu gọn giới thiệu')

    act(() => {
      button.click()
    })

    expect(button.textContent).toContain('Tìm hiểu cách hoạt động')
    expect(host.textContent).not.toContain('Cách học truyền thống')
    expect(localStorage.getItem('flama_intro_yomitan_collapsed')).toBe('true')

    // Click again to expand
    act(() => {
      button.click()
    })

    expect(button.textContent).toContain('Thu gọn giới thiệu')
    expect(host.textContent).toContain('Cách học truyền thống')
    expect(localStorage.getItem('flama_intro_yomitan_collapsed')).toBe('false')
  })

  it('renders AsbplayerValueIntro, supports onStartSetup callback, and toggles collapse state', () => {
    const onStartSetup = vi.fn()
    act(() => {
      root.render(<AsbplayerValueIntro onStartSetup={onStartSetup} />)
    })

    expect(host.textContent).toContain('Cao thủ luyện nghe')
    expect(host.textContent).toContain('Tại sao nên kết hợp asbplayer cùng Flama?')
    expect(host.textContent).toContain('Xem phim truyền thống')
    expect(host.textContent).toContain('Khi kết hợp cùng Flama')
    expect(host.textContent).toContain('Tự động cắt đúng file MP3')

    const ctaBtn = Array.from(host.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đi đến Cài đặt & Tạo Token kết nối'),
    )
    expect(ctaBtn).toBeDefined()
    act(() => {
      ctaBtn?.click()
    })
    expect(onStartSetup).toHaveBeenCalledTimes(1)

    const button = host.querySelector('button')!
    expect(button.textContent).toContain('Thu gọn giới thiệu')

    act(() => {
      button.click()
    })

    expect(button.textContent).toContain('Tìm hiểu cách hoạt động')
    expect(host.textContent).not.toContain('Xem phim truyền thống')
    expect(localStorage.getItem('flama_intro_asbplayer_collapsed')).toBe('true')
  })

  it('renders McpValueIntro and toggles collapse state', () => {
    act(() => {
      root.render(<McpValueIntro />)
    })

    expect(host.textContent).toContain('Gia sư AI riêng cho Flama')
    expect(host.textContent).toContain('Tại sao nên kết nối Trợ lý AI cùng Flama?')
    expect(host.textContent).toContain('Chat AI thông thường')
    expect(host.textContent).toContain('Khi kết nối cùng Flama (MCP)')
    expect(host.textContent).toContain('Tạo hàng chục thẻ chỉ bằng 1 câu lệnh')

    const button = host.querySelector('button')!
    expect(button.textContent).toContain('Thu gọn giới thiệu')

    act(() => {
      button.click()
    })

    expect(button.textContent).toContain('Tìm hiểu cách hoạt động')
    expect(host.textContent).not.toContain('Chat AI thông thường')
    expect(localStorage.getItem('flama_intro_mcp_collapsed')).toBe('true')
  })
})

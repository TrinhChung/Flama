// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TemplateCoherenceBanner } from '../components/TemplateCoherenceBanner'
import type { TemplateCoherenceWarning } from '@/entities/deck-version'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const sampleWarnings: TemplateCoherenceWarning[] = [
  {
    template_id: 'tmpl_responsive_1',
    template_name: 'Very Long Advanced Card Template Name for Japanese Kanji & Vocabulary Exercises',
    warning_type: 'OUTDATED_PIN',
    pinned_release: 'v1.0.0',
    latest_release: 'v2.0.0',
    message: 'Phiên bản mẫu thẻ hiện tại đã quá cũ so với cấu trúc mới của loại thẻ này, có thể gây lỗi hiển thị trong chế độ ôn tập ban đêm.',
    action_recommendation: 'Cập nhật ngay lên phiên bản v2.0.0 để tương thích với các trường dữ liệu và âm thanh mới.',
  },
]

describe('TemplateCoherenceBanner — Responsive Multi-Device Tests (R4)', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  it('Mobile (375px): wraps CTA button gracefully, expands touch target, and applies break-words/truncate', async () => {
    window.innerWidth = 375
    window.innerHeight = 667
    window.dispatchEvent(new Event('resize'))

    const onAlign = vi.fn()

    await act(async () => {
      root.render(
        <TemplateCoherenceBanner
          warnings={sampleWarnings}
          onAlignTemplatePin={onAlign}
          onDismiss={vi.fn()}
        />
      )
    })

    // 1. Header spacing has gap-2 sm:gap-3
    const headerRow = container.querySelector('.flex.items-start.gap-2') as HTMLDivElement
    expect(headerRow).not.toBeNull()
    expect(headerRow.className).toContain('gap-2')
    expect(headerRow.className).toContain('sm:gap-3')

    // 2. Warning item layout has flex-col sm:flex-row and gap-2 sm:gap-3
    const warningItem = container.querySelector('[data-testid="coherence-warning-tmpl_responsive_1"]') as HTMLDivElement
    expect(warningItem).not.toBeNull()
    expect(warningItem.className).toContain('flex-col')
    expect(warningItem.className).toContain('sm:flex-row')
    expect(warningItem.className).toContain('gap-2')
    expect(warningItem.className).toContain('sm:gap-3')

    // 3. Template name has truncate and title attribute
    const titleEl = warningItem.querySelector('span.truncate')
    expect(titleEl).not.toBeNull()
    expect(titleEl?.getAttribute('title')).toContain('Very Long Advanced Card Template Name')

    // 4. Message and recommendation have break-words
    const messageEl = warningItem.querySelector('p.text-muted-foreground')
    expect(messageEl?.className).toContain('break-words')

    const recEl = warningItem.querySelector('p.text-amber-800')
    expect(recEl?.className).toContain('break-words')

    // 5. CTA button has mobile full-width wrap, whitespace-normal, and touch target >= 36px
    const ctaBtn = container.querySelector('[data-testid="align-template-pin-tmpl_responsive_1"]') as HTMLButtonElement
    expect(ctaBtn).not.toBeNull()
    expect(ctaBtn.className).toContain('w-full')
    expect(ctaBtn.className).toContain('sm:w-auto')
    expect(ctaBtn.className).toContain('whitespace-normal')
    expect(ctaBtn.className).toContain('sm:whitespace-nowrap')
    expect(ctaBtn.className).toContain('min-h-[36px]')
    expect(ctaBtn.className).toContain('sm:min-h-[28px]')

    // Clicking CTA triggers callback
    await act(async () => {
      ctaBtn.click()
    })
    expect(onAlign).toHaveBeenCalledWith('tmpl_responsive_1', 'v2.0.0')
  })

  it('Desktop (1280px): displays aligned single-line CTA and badges with pin transition', async () => {
    window.innerWidth = 1280
    window.innerHeight = 800
    window.dispatchEvent(new Event('resize'))

    await act(async () => {
      root.render(
        <TemplateCoherenceBanner
          warnings={sampleWarnings}
          onAlignTemplatePin={vi.fn()}
        />
      )
    })

    const alertBanner = container.querySelector('[role="alert"]') as HTMLDivElement
    expect(alertBanner).not.toBeNull()

    // Status badge has normalized h-4 height
    const badge = container.querySelector('.text-\\[10px\\].h-4')
    expect(badge).not.toBeNull()
    expect(badge?.textContent).toContain('Có bản mới')

    // Pin version and latest arrow
    expect(container.textContent).toContain('pin: v1.0.0')
    expect(container.textContent).toContain('mới nhất: v2.0.0')
  })
})

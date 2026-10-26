// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TemplateCoherenceBanner } from './TemplateCoherenceBanner'
import type { TemplateCoherenceWarning } from '@/entities/deck-version'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('TemplateCoherenceBanner — Adversarial Stress Suite', () => {
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

  it('ADVERSARIAL: Returns null when warnings is empty, null, or undefined', async () => {
    // 1. Empty array
    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={[]} />)
    })
    expect(container.innerHTML).toBe('')

    // 2. Null (defensive check)
    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={null as unknown as TemplateCoherenceWarning[]} />)
    })
    expect(container.innerHTML).toBe('')

    // 3. Undefined (defensive check)
    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={undefined as unknown as TemplateCoherenceWarning[]} />)
    })
    expect(container.innerHTML).toBe('')
  })

  it('ADVERSARIAL: Properly handles standard warning types with accurate badges', async () => {
    const warnings: TemplateCoherenceWarning[] = [
      {
        template_id: 'tmpl_outdated',
        template_name: 'Outdated Template',
        warning_type: 'OUTDATED_PIN',
        pinned_release: 'v1.0',
        latest_release: 'v2.0',
        message: 'Có bản phát hành mới hơn trên thư viện.',
        action_recommendation: 'Cập nhật lên v2.0 để sửa lỗi CSS.',
      },
      {
        template_id: 'tmpl_draft',
        template_name: 'Draft Template',
        warning_type: 'UNCOMMITTED_DRAFT',
        pinned_release: 'v1.0',
        latest_release: 'v1.0',
        message: 'Mẫu thẻ có bản nháp chưa công bố.',
        action_recommendation: 'Xuất bản bản nháp trước khi phát hành Note Type.',
      },
      {
        template_id: 'tmpl_unmapped',
        template_name: 'Unmapped Template',
        warning_type: 'UNMAPPED_FIELDS',
        pinned_release: 'v1.5',
        latest_release: 'v1.5',
        message: 'Thiếu ánh xạ cho trường Audio.',
      },
    ]

    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={warnings} />)
    })

    // Header count
    expect(container.textContent).toContain('Phát hiện 3 Mẫu thẻ gắn kèm')

    // Badges
    expect(container.textContent).toContain('Có bản mới')
    expect(container.textContent).toContain('Bản nháp chưa công bố')
    expect(container.textContent).toContain('Chưa ánh xạ trường')

    // Version transitions
    expect(container.textContent).toContain('pin: v1.0')
    expect(container.textContent).toContain('mới nhất: v2.0')

    // Recommendations
    expect(container.textContent).toContain('💡 Gợi ý: Cập nhật lên v2.0 để sửa lỗi CSS.')
    expect(container.textContent).toContain('💡 Gợi ý: Xuất bản bản nháp trước khi phát hành Note Type.')
  })

  it('ADVERSARIAL: Fallback behavior for custom/unknown warning types and edge cases', async () => {
    const edgeCaseWarnings: TemplateCoherenceWarning[] = [
      {
        template_id: 'tmpl_custom_type',
        template_name: 'Custom Type Template',
        warning_type: 'UNKNOWN_CUSTOM_CODE' as unknown as 'OUTDATED_PIN',
        message: 'Cảnh báo tùy chỉnh không nằm trong enum',
      },
      {
        template_id: 'tmpl_empty_type',
        template_name: 'Empty Type Template',
        warning_type: '' as unknown as 'OUTDATED_PIN',
        message: 'Empty string warning type',
      },
      {
        template_id: 'tmpl_same_version',
        template_name: 'Same Version Template',
        warning_type: 'OUTDATED_PIN',
        pinned_release: 'v1.0.0',
        latest_release: 'v1.0.0', // Same version, should NOT display arrow transition
        message: 'Pinned version is identical to latest',
      },
    ]

    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={edgeCaseWarnings} />)
    })

    // Custom warning label falls back to literal string
    expect(container.textContent).toContain('UNKNOWN_CUSTOM_CODE')

    // Same version does not show "mới nhất: v1.0.0" arrow indicator
    expect(container.textContent).not.toContain('→ mới nhất: v1.0.0')
  })

  it('ADVERSARIAL: Injection attacks (Mustache, HTML, XSS) in warnings are rendered strictly as text', async () => {
    const maliciousWarnings: TemplateCoherenceWarning[] = [
      {
        template_id: 'tmpl_evil',
        template_name: '<script>alert("tpl_xss")</script>',
        warning_type: 'OUTDATED_PIN',
        pinned_release: '{{front}}',
        latest_release: '{{back}}',
        message: '<img src=x onerror=steal()> {{#Block}}leak{{/Block}}',
        action_recommendation: '<b onclick=hack()>Click here to exploit</b>',
      },
    ]

    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={maliciousWarnings} />)
    })

    // Absolutely no script, img, or bold elements generated from the strings
    expect(container.querySelectorAll('script').length).toBe(0)
    expect(container.querySelectorAll('img').length).toBe(0)
    expect(container.querySelectorAll('b[onclick]').length).toBe(0)

    // Escaped string literals are preserved
    expect(container.textContent).toContain('<script>alert("tpl_xss")</script>')
    expect(container.textContent).toContain('<img src=x onerror=steal()>')
    expect(container.textContent).toContain('{{#Block}}leak{{/Block}}')
  })

  it('ADVERSARIAL: Callback execution and optional CTA omission', async () => {
    const onAlignTemplatePin = vi.fn()
    const onDismiss = vi.fn()

    const warning: TemplateCoherenceWarning = {
      template_id: 'tmpl_align_target',
      template_name: 'Target Template',
      warning_type: 'OUTDATED_PIN',
      pinned_release: 'v1.0',
      latest_release: 'v2.5',
      message: 'Needs alignment',
    }

    // 1. Render with callbacks
    await act(async () => {
      root.render(
        <TemplateCoherenceBanner
          warnings={[warning]}
          onAlignTemplatePin={onAlignTemplatePin}
          onDismiss={onDismiss}
        />
      )
    })

    // Click Align CTA
    const alignBtn = container.querySelector<HTMLButtonElement>(
      '[data-testid="align-template-pin-tmpl_align_target"]'
    )
    expect(alignBtn).not.toBeNull()
    await act(async () => {
      alignBtn?.click()
    })
    expect(onAlignTemplatePin).toHaveBeenCalledWith('tmpl_align_target', 'v2.5')

    // Click Dismiss
    const dismissBtn = container.querySelector<HTMLButtonElement>('button[aria-label="Đóng cảnh báo"]')
    expect(dismissBtn).not.toBeNull()
    await act(async () => {
      dismissBtn?.click()
    })
    expect(onDismiss).toHaveBeenCalledTimes(1)

    // 2. Render without callbacks: buttons must NOT be rendered
    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={[warning]} />)
    })
    expect(container.querySelector('[data-testid^="align-template-pin-"]')).toBeNull()
    expect(container.querySelector('button[aria-label="Đóng cảnh báo"]')).toBeNull()
  })

  it('ADVERSARIAL: Duplicate template IDs and high volume (50 warnings) with key collision resilience', async () => {
    // 25 templates with 2 warnings each = 50 warnings with duplicate template_id
    const duplicateWarnings: TemplateCoherenceWarning[] = []
    for (let i = 0; i < 25; i++) {
      duplicateWarnings.push({
        template_id: `tmpl_dup_${i}`,
        template_name: `Template ${i}`,
        warning_type: 'OUTDATED_PIN',
        pinned_release: 'v1.0',
        latest_release: 'v2.0',
        message: `Outdated pin warning for ${i}`,
      })
      duplicateWarnings.push({
        template_id: `tmpl_dup_${i}`,
        template_name: `Template ${i}`,
        warning_type: 'UNMAPPED_FIELDS',
        pinned_release: 'v1.0',
        latest_release: 'v2.0',
        message: `Unmapped fields warning for ${i}`,
      })
    }

    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={duplicateWarnings} />)
    })

    const items = container.querySelectorAll('[data-testid^="coherence-warning-"]')
    expect(items.length).toBe(50)
  })

  it('ADVERSARIAL: Accessibility role="alert" verification', async () => {
    const warning: TemplateCoherenceWarning = {
      template_id: 'tmpl_a11y',
      template_name: 'A11y Template',
      warning_type: 'OUTDATED_PIN',
      message: 'A11y message',
    }

    await act(async () => {
      root.render(<TemplateCoherenceBanner warnings={[warning]} />)
    })

    const alertElement = container.querySelector('[role="alert"]')
    expect(alertElement).not.toBeNull()
  })
})

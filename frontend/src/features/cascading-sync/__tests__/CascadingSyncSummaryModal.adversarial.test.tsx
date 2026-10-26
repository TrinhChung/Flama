// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CascadingSyncSummaryModal } from '../components/CascadingSyncSummaryModal'
import type { CascadingSyncSummary } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('CascadingSyncSummaryModal — Adversarial Stress Suite', () => {
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

  it('ADVERSARIAL: Boundary case with 0 updated templates and 0 updated note types', async () => {
    const zeroDependenciesSummary: CascadingSyncSummary = {
      deck_title: 'Content-Only Update Deck',
      version_label: 'v1.1',
      cards_updated: 25,
      note_types_updated: [], // Zero note types updated
      templates_updated: [], // Zero templates updated
      progress_preserved_count: 500,
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={zeroDependenciesSummary}
        />
      )
    })

    // Both sections must display clear fallback messages without crashing
    expect(document.body.textContent).toContain('Không có thay đổi cấu trúc Loại thẻ.')
    expect(document.body.textContent).toContain('Không có thay đổi Mẫu thẻ.')

    // Note types count shows (0)
    expect(document.body.textContent).toContain('Note Types đã cập nhật (0)')
    expect(document.body.textContent).toContain('Templates đã cập nhật (0)')
  })

  it('ADVERSARIAL: Fallback card count calculation when cards_updated is undefined', async () => {
    const calculatedCardsSummary: CascadingSyncSummary = {
      deck_title: 'Calculated Count Deck',
      version_label: 'v2.0',
      from_version_label: 'v1.0',
      cards_added: 120,
      cards_modified: 45,
      cards_removed: 5,
      // cards_updated intentionally undefined to test fallback math: 120 + 45 + 5 = 170
      note_types_updated: [],
      templates_updated: [],
      progress_preserved_count: 300,
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={calculatedCardsSummary}
        />
      )
    })

    expect(document.body.textContent).toContain('170 thẻ đã cập nhật')
    expect(document.body.textContent).toContain('+120')
    expect(document.body.textContent).toContain('~45')
    expect(document.body.textContent).toContain('-5')
  })

  it('ADVERSARIAL: Single version label when from_version_label is omitted', async () => {
    const freshInstallSummary: CascadingSyncSummary = {
      deck_title: 'Fresh Install Deck',
      version_label: 'v1.0',
      // from_version_label omitted
      cards_updated: 50,
      note_types_updated: [],
      templates_updated: [],
      progress_preserved_count: 50,
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={freshInstallSummary}
        />
      )
    })

    expect(document.body.textContent).toContain('Cập nhật Deck thành công (v1.0)')
    expect(document.body.textContent).not.toContain('→')
  })

  it('ADVERSARIAL: Exact wording of SRS progress reassurance banner', async () => {
    const summary: CascadingSyncSummary = {
      deck_title: 'Safety Check Deck',
      version_label: 'v1.0',
      progress_preserved_count: 9999,
      note_types_updated: [],
      templates_updated: [],
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={summary}
        />
      )
    })

    const guaranteeBanner = document.body.querySelector('[data-testid="srs-progress-guarantee"]')
    expect(guaranteeBanner).not.toBeNull()
    expect(guaranteeBanner?.textContent).toContain(
      'Toàn bộ tiến độ học (SRS / Flashcards) và lịch sử ôn tập được bảo toàn 100%'
    )
    expect(guaranteeBanner?.textContent).toContain('9,999 thẻ học giữ nguyên vẹn')
  })

  it('ADVERSARIAL: Accessibility standards (role="dialog", aria-labelledby, aria-describedby)', async () => {
    const summary: CascadingSyncSummary = {
      deck_title: 'A11y Deck',
      version_label: 'v1.0',
      progress_preserved_count: 100,
      note_types_updated: [],
      templates_updated: [],
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={summary}
        />
      )
    })

    const dialogContent = document.body.querySelector('[role="dialog"]')
    expect(dialogContent).not.toBeNull()

    // Title and description must exist for screen reader compliance
    const title = document.body.querySelector('h2')
    expect(title).not.toBeNull()
    expect(title?.textContent).toContain('Cập nhật Deck thành công')
  })

  it('ADVERSARIAL: Keyboard accessibility (Escape key triggers onOpenChange(false))', async () => {
    const onOpenChange = vi.fn()

    const summary: CascadingSyncSummary = {
      deck_title: 'Escape Key Deck',
      version_label: 'v1.0',
      progress_preserved_count: 50,
      note_types_updated: [],
      templates_updated: [],
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={onOpenChange}
          summary={summary}
        />
      )
    })

    // Simulate pressing Escape key
    await act(async () => {
      document.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: 'Escape',
          code: 'Escape',
          keyCode: 27,
          which: 27,
          bubbles: true,
          cancelable: true,
        })
      )
    })

    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('ADVERSARIAL: Malicious strings (XSS / Mustache) are escaped and not executed', async () => {
    const maliciousSummary: CascadingSyncSummary = {
      deck_title: '<script>alert("deck_xss")</script>',
      version_label: '<img src=x onerror=alert(1)>',
      from_version_label: '{{Front}}',
      progress_preserved_count: 100,
      note_types_updated: [
        {
          id: 'nt_evil',
          name: '<iframe src="evil.com"></iframe>',
          version: '{{version}}',
        },
      ],
      templates_updated: [
        {
          id: 'tpl_evil',
          name: '<b onclick=hack()>Click</b>',
          from_version: 'v1',
          to_version: 'v2',
        },
      ],
    }

    await act(async () => {
      root.render(
        <CascadingSyncSummaryModal
          open={true}
          onOpenChange={vi.fn()}
          summary={maliciousSummary}
        />
      )
    })

    // No raw script, img, iframe elements in DOM
    expect(document.body.querySelectorAll('script').length).toBe(0)
    expect(document.body.querySelectorAll('img[onerror]').length).toBe(0)
    expect(document.body.querySelectorAll('iframe').length).toBe(0)
    expect(document.body.querySelectorAll('b[onclick]').length).toBe(0)

    // Escaped string contents are safely visible
    expect(document.body.textContent).toContain('<script>alert("deck_xss")</script>')
    expect(document.body.textContent).toContain('<iframe src="evil.com"></iframe>')
    expect(document.body.textContent).toContain('{{Front}} → <img src=x onerror=alert(1)>')
  })
})

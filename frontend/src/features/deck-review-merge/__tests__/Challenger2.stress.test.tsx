// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createRoot, type Root } from 'react-dom/client'
import { act } from 'react'
import type { CardDiff as CardDiffItemType } from '@/entities/card-diff'
import { HighVolumeDiffWorkspace } from '../components/HighVolumeDiffWorkspace'
import { CardDiffItem } from '../components/CardDiffItem'
import { NoteTypeDiffGroup } from '../components/NoteTypeDiffGroup'
import { DeckStructuralDependenciesCard } from '@/features/deck-versioning/components/DeckStructuralDependenciesCard'
import { TemplateCoherenceBanner } from '@/features/note-types/components/TemplateCoherenceBanner'
import { CascadingSyncSummaryModal } from '@/features/cascading-sync/components/CascadingSyncSummaryModal'

describe('Challenger 2 — Adversarial Stress Testing (High-Volume, Edge Cases, OKLCH Contrast)', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root?.unmount()
    })
    container?.remove()
    container = null
    root = null
    vi.restoreAllMocks()
  })

  // =========================================================================
  // CHALLENGE SET 1: Extreme Data Scenarios & Character Edge Cases
  // =========================================================================
  describe('Challenge Set 1: Extreme Data Scenarios & Text Truncation / Tooltip Safety', () => {
    const specialUnicodeName = '𠮷野家・𩸽定食 👨‍👩‍👧‍👦 🎌🗾✨'
    const longKanjiText = '親譲りの無鉄砲で小供の時から損ばかりしている'.repeat(10) // 240+ chars
    const htmlInjectionPayload = '<script>alert("xss")</script><img src=x onerror=alert(1)>'

    it('CardDiffItem renders special Unicode, long Kanji, and HTML injection safely without unescaped tags', async () => {
      const item: CardDiffItemType = {
        id: 'edge_card_1',
        noteId: 'note_1',
        noteTypeId: 'nt_1',
        noteTypeName: specialUnicodeName,
        changeType: 'modified',
        primaryText: htmlInjectionPayload,
        secondaryText: longKanjiText,
        fieldDiffs: [
          {
            fieldName: '<svg onload=alert(2)>',
            before: '前：' + specialUnicodeName,
            after: '後：' + htmlInjectionPayload,
            isConflict: true,
          },
        ],
      }

      await act(async () => {
        root?.render(<CardDiffItem item={item} isSelected={false} onToggle={vi.fn()} />)
      })

      // 1. Check title attributes for text truncation support
      const primarySpan = container?.querySelector('span.truncate')
      expect(primarySpan).not.toBeNull()
      expect(primarySpan?.getAttribute('title')).toBe(htmlInjectionPayload)
      expect(primarySpan?.textContent).toBe(htmlInjectionPayload)

      // Ensure no actual script or img element was created in DOM (XSS prevention)
      expect(container?.querySelector('script')).toBeNull()
      expect(container?.querySelector('img')).toBeNull()
      expect(container?.querySelector('svg[onload]')).toBeNull()

      // 2. Expand details and check field diffs
      const detailsBtn = container?.querySelector('[data-testid="toggle-details-edge_card_1"]') as HTMLButtonElement
      expect(detailsBtn).not.toBeNull()
      await act(async () => {
        detailsBtn.click()
      })

      const diffContainer = container?.querySelector('[data-testid="field-diffs-container-edge_card_1"]')
      expect(diffContainer).not.toBeNull()
      expect(diffContainer?.textContent).toContain('<svg onload=alert(2)>')
      expect(diffContainer?.textContent).toContain(specialUnicodeName)
      expect(diffContainer?.textContent).toContain(htmlInjectionPayload)
    })

    it('NoteTypeDiffGroup handles long Kanji and HTML payload in group title with truncation and title tooltip', async () => {
      const group = {
        noteTypeId: 'nt_edge_1',
        noteTypeName: `${htmlInjectionPayload} - ${longKanjiText}`,
        totalCount: 5,
        addedCount: 2,
        modifiedCount: 2,
        removedCount: 1,
        conflictCount: 0,
        items: [],
      }

      await act(async () => {
        root?.render(
          <NoteTypeDiffGroup
            group={group}
            isCollapsed={false}
            allSelected={false}
            someSelected={false}
            onToggleCollapse={vi.fn()}
            onToggleSelectGroup={vi.fn()}
          />
        )
      })

      const groupTitleSpan = container?.querySelector('span.truncate')
      expect(groupTitleSpan).not.toBeNull()
      expect(groupTitleSpan?.getAttribute('title')).toBe(group.noteTypeName)
      expect(container?.querySelector('script')).toBeNull()
    })

    it('DeckStructuralDependenciesCard handles extreme Unicode and long titles with title tooltip and truncation', async () => {
      await act(async () => {
        root?.render(
          <DeckStructuralDependenciesCard
            deckTitle={`${specialUnicodeName} - ${htmlInjectionPayload}`}
            currentVersionLabel="v2.0.0-edge"
            noteTypes={[
              {
                note_type_id: 'nt_1',
                note_type_name: longKanjiText,
                note_count: 100,
                pinned_version_label: 'v1.0.0',
                latest_version_label: 'v1.1.0',
                status: 'update_available',
                has_draft_changes: false,
                templates: [
                  {
                    template_id: 'tpl_1',
                    template_name: `<script>/*tpl*/</script>${specialUnicodeName}`,
                    occurrence_key: 'front_main',
                    pinned_version_label: 'v1.0.0',
                    latest_version_label: 'v1.2.0',
                    status: 'update_available',
                    has_newer_release: true,
                    has_uncommitted_draft: false,
                  },
                ],
              },
            ]}
          />
        )
      })

      // Deck title has title attribute and break-words
      const deckTitleElem = container?.querySelector('span[title]')
      expect(deckTitleElem?.getAttribute('title')).toBe(`${specialUnicodeName} - ${htmlInjectionPayload}`)
      expect(deckTitleElem?.className).toContain('break-words')

      // Note type title has title and truncate
      const ntTitle = container?.querySelector('span[title="' + longKanjiText + '"]')
      expect(ntTitle).not.toBeNull()
      expect(ntTitle?.className).toContain('truncate')

      // Template title has title and truncate
      const tplTitle = container?.querySelector('span[title*="tpl"]')
      expect(tplTitle).not.toBeNull()
      expect(tplTitle?.className).toContain('truncate')
      expect(container?.querySelector('script')).toBeNull()
    })

    it('TemplateCoherenceBanner renders warnings with extreme payloads safely', async () => {
      await act(async () => {
        root?.render(
          <TemplateCoherenceBanner
            warnings={[
              {
                template_id: 'tpl_warn_1',
                template_name: `<b onclick="alert(1)">${specialUnicodeName}</b>`,
                warning_type: 'OUTDATED_PIN',
                pinned_release: 'v1.0.0',
                latest_release: 'v2.0.0',
                message: htmlInjectionPayload,
                action_recommendation: longKanjiText,
              },
            ]}
          />
        )
      })

      const warningTitle = container?.querySelector('[data-testid="coherence-warning-tpl_warn_1"] span.truncate')
      expect(warningTitle).not.toBeNull()
      expect(warningTitle?.getAttribute('title')).toContain(specialUnicodeName)
      expect(container?.querySelector('script')).toBeNull()
      expect(container?.querySelector('b[onclick]')).toBeNull()
    })

    it('CascadingSyncSummaryModal handles extreme deck and note type names with truncation and tooltips', async () => {
      await act(async () => {
        root?.render(
          <CascadingSyncSummaryModal
            open={true}
            onOpenChange={vi.fn()}
            summary={{
              deck_id: 'deck_1',
              deck_title: `${specialUnicodeName} ${longKanjiText}`,
              version_label: 'v2.0.0',
              from_version_label: 'v1.0.0',
              progress_preserved_count: 1250,
              cards_updated: 45,
              cards_added: 20,
              cards_modified: 20,
              cards_removed: 5,
              note_types_updated: [
                { id: 'nt_1', name: `<script>nt</script>${longKanjiText}`, version: 'v2.0' },
              ],
              templates_updated: [
                { id: 'tpl_1', name: htmlInjectionPayload, from_version: 'v1.0', to_version: 'v2.0' },
              ],
            }}
          />
        )
      })

      const allSpans = Array.from(document.body.querySelectorAll('span[title]'))
      const deckTitleElem = allSpans.find((el) => el.getAttribute('title')?.includes('𠮷野家'))
      expect(deckTitleElem).toBeDefined()
      expect(deckTitleElem?.className).toContain('break-words')

      // Note type item has truncate and title
      const ntSpan = allSpans.find((el) => el.getAttribute('title')?.includes('nt</script>'))
      expect(ntSpan).toBeDefined()
      expect(ntSpan?.className).toContain('truncate')

      // Template item has truncate and title
      const tplSpan = allSpans.find((el) => el.getAttribute('title') === htmlInjectionPayload)
      expect(tplSpan).toBeDefined()
      expect(tplSpan?.className).toContain('truncate')
      expect(document.body.querySelector('script')).toBeNull()
    })
  })

  // =========================================================================
  // CHALLENGE SET 2: Virtualization, Search Bypass & Deep Scroll Filtering
  // =========================================================================
  describe('Challenge Set 2: Virtualization, Search Bypass & Deep Scroll Filtering', () => {
    function generateItems(count: number): CardDiffItemType[] {
      return Array.from({ length: count }, (_, i) => ({
        id: `card_${i}`,
        noteId: `note_${i}`,
        noteTypeId: `nt_${i % 5}`,
        noteTypeName: `Note Type ${i % 5}`,
        changeType: (['added', 'modified', 'removed'] as const)[i % 3],
        primaryText: `Word #${i} 日本語`,
        secondaryText: `Meaning #${i}`,
      }))
    }

    it('Ctrl+F bypasses virtualization and Escape / container scroll restores it cleanly', async () => {
      const items = generateItems(100)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const initialCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(initialCards!.length).toBeLessThan(150)

      // 1. Fire Ctrl+F -> bypasses virtualization
      await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
      })

      const allRenderedCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(allRenderedCards!.length).toBe(100)

      // 2. Press Escape -> restores virtualization
      await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
      })

      const recoveredCards = container?.querySelectorAll('[data-testid^="card-diff-item-"]')
      expect(recoveredCards!.length).toBeLessThan(150)

      // 3. Fire Ctrl+F again
      await act(async () => {
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
      })
      expect(container?.querySelectorAll('[data-testid^="card-diff-item-"]')!.length).toBe(100)

      // 4. Scroll container -> also restores virtualization
      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]'
      ) as HTMLDivElement
      expect(scrollContainer).not.toBeNull()

      await act(async () => {
        scrollContainer.dispatchEvent(new Event('scroll'))
      })

      expect(container?.querySelectorAll('[data-testid^="card-diff-item-"]')!.length).toBeLessThan(150)
    })

    it('adversarial probe: deep scroll to 40,000px then filter to 1 item does NOT crash and renders the item', async () => {
      const items = generateItems(1000)

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]'
      ) as HTMLDivElement
      expect(scrollContainer).not.toBeNull()

      Object.defineProperty(scrollContainer, 'clientHeight', { value: 600, configurable: true })

      // Scroll deep: 40,000px
      await act(async () => {
        scrollContainer.scrollTop = 40000
        scrollContainer.dispatchEvent(new Event('scroll'))
      })

      // Now apply a strict search query that matches only 1 item: "Word #999"
      const searchInput = container?.querySelector('input[type="search"]') as HTMLInputElement
      expect(searchInput).not.toBeNull()

      await act(async () => {
        const nativeSetter = Object.getOwnPropertyDescriptor(
          window.HTMLInputElement.prototype,
          'value'
        )?.set
        nativeSetter?.call(searchInput, 'Word #999')
        searchInput.dispatchEvent(new Event('input', { bubbles: true }))
        searchInput.dispatchEvent(new Event('change', { bubbles: true }))
        // Wait for debounce (200ms)
        await new Promise((resolve) => setTimeout(resolve, 300))
      })

      // Verify the 1 matching card is rendered and workspace did not throw or blow up
      const filteredCard = container?.querySelector('[data-testid="card-diff-item-card_999"]')
      expect(filteredCard).not.toBeNull()
      expect(filteredCard?.textContent).toContain('Word #999')

      // Ensure padding top and bottom are finite non-negative numbers
      const spacerTop = container?.querySelector('[data-testid="virtual-spacer-top"]') as HTMLDivElement
      const spacerBottom = container?.querySelector('[data-testid="virtual-spacer-bottom"]') as HTMLDivElement
      expect(parseInt(spacerTop?.style.height || '0', 10)).toBeGreaterThanOrEqual(0)
      expect(parseInt(spacerBottom?.style.height || '0', 10)).toBeGreaterThanOrEqual(0)
    })
  })

  // =========================================================================
  // CHALLENGE SET 3: Flama OKLCH Theme Contrast & Semantic Token Compliance
  // =========================================================================
  describe('Challenge Set 3: Flama Warm Palette & WCAG AA Contrast Compliance', () => {
    it('verifies modified status badges use warm amber tokens instead of blue', async () => {
      const item: CardDiffItemType = {
        id: 'card_mod_1',
        noteId: 'n1',
        noteTypeId: 'nt1',
        noteTypeName: 'Vocabulary',
        changeType: 'modified',
        primaryText: '猫',
        secondaryText: 'Con mèo',
      }

      await act(async () => {
        root?.render(<CardDiffItem item={item} isSelected={false} onToggle={vi.fn()} />)
      })

      const badge = container?.querySelector('.capitalize')
      expect(badge?.className).toContain('text-amber-800')
      expect(badge?.className).toContain('dark:text-amber-300')
      expect(badge?.className).toContain('bg-amber-500/10')
      expect(badge?.className).not.toContain('text-blue')
    })

    it('verifies active amber filter button has high contrast (text-amber-950 font-bold bg-amber-500)', async () => {
      const items: CardDiffItemType[] = [
        {
          id: 'card_1',
          noteId: 'n1',
          noteTypeId: 'nt1',
          noteTypeName: 'Vocabulary',
          changeType: 'modified',
          primaryText: '犬',
          secondaryText: 'Con chó',
        },
      ]

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      // Click "Đã sửa" filter button
      const modifiedFilterBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
        b.textContent?.includes('Đã sửa')
      )
      expect(modifiedFilterBtn).toBeDefined()

      await act(async () => {
        modifiedFilterBtn?.click()
      })

      // Check active classes on modified filter button
      expect(modifiedFilterBtn?.className).toContain('bg-amber-500')
      expect(modifiedFilterBtn?.className).toContain('text-amber-950')
      expect(modifiedFilterBtn?.className).toContain('font-bold')
      expect(modifiedFilterBtn?.className).toContain('border-amber-600')
    })

    it('verifies mathematical WCAG AA contrast ratio compliance for all status tokens', () => {
      function srgbToLin(c: number): number {
        const val = c / 255
        return val <= 0.04045 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4)
      }

      function lum(hex: string): number {
        const r = parseInt(hex.slice(1, 3), 16)
        const g = parseInt(hex.slice(3, 5), 16)
        const b = parseInt(hex.slice(5, 7), 16)
        return 0.2126 * srgbToLin(r) + 0.7152 * srgbToLin(g) + 0.0722 * srgbToLin(b)
      }

      function contrastRatio(h1: string, h2: string): number {
        const l1 = lum(h1)
        const l2 = lum(h2)
        return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
      }

      const whiteBg = '#ffffff'
      const darkBg = '#18181b' // standard dark card background

      // Active amber pill: amber-950 on amber-500
      const activeAmberPillContrast = contrastRatio('#451a03', '#f59e0b')
      expect(activeAmberPillContrast).toBeGreaterThanOrEqual(4.5) // 6.97:1

      // Modified badge: amber-800 on white (Light) and amber-300 on darkBg (Dark)
      const modifiedLight = contrastRatio('#92400e', whiteBg)
      const modifiedDark = contrastRatio('#fcd34d', darkBg)
      expect(modifiedLight).toBeGreaterThanOrEqual(4.5) // 7.09:1
      expect(modifiedDark).toBeGreaterThanOrEqual(4.5) // 12.29:1

      // Added badge: emerald-700 on white (Light) and emerald-300 on darkBg (Dark)
      const addedLight = contrastRatio('#047857', whiteBg)
      const addedDark = contrastRatio('#6ee7b7', darkBg)
      expect(addedLight).toBeGreaterThanOrEqual(4.5) // 5.48:1
      expect(addedDark).toBeGreaterThanOrEqual(4.5) // 11.62:1

      // Removed badge: rose-700 on white (Light) and rose-300 on darkBg (Dark)
      const removedLight = contrastRatio('#be123c', whiteBg)
      const removedDark = contrastRatio('#fda4af', darkBg)
      expect(removedLight).toBeGreaterThanOrEqual(4.5) // 6.29:1
      expect(removedDark).toBeGreaterThanOrEqual(4.5) // 9.37:1
    })
  })
})

// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CardDiff } from '@/entities/card-diff'
import { HighVolumeDiffWorkspace } from '../components/HighVolumeDiffWorkspace'
import { CardDiffItem } from '../components/CardDiffItem'
import { DiffFilterToolbar } from '../components/DiffFilterToolbar'
import { BatchActionBar } from '../components/BatchActionBar'
import { NoteTypeDiffGroup } from '../components/NoteTypeDiffGroup'
import { DeckStructuralDependenciesCard } from '../../deck-versioning/components/DeckStructuralDependenciesCard'
import { TemplateCoherenceBanner } from '../../note-types/components/TemplateCoherenceBanner'
import { CascadingSyncSummaryModal } from '../../cascading-sync/components/CascadingSyncSummaryModal'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const UNBROKEN_SUPER_LONG_STRING =
  'Supercalifragilisticexpialidocious_UnbrokenStringWithoutAnySpaces1234567890_VeryLongIdentifier_VocabularyCardNoteTypeAndTemplateCombination_ExtraLength_TestingOverflow'

const JAPANESE_EXTREME_STRING =
  '【完全網羅】JLPT N1・N2・N3 頻出語彙マスター20000語・例文付き・音声対応・文法解説・コロケーション・慣用句・類義語対比・四字熟語完全収録ノートタイプ'

describe('CHALLENGER 1: Adversarial Responsive & Viewport Layout Stress Harness', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    if (root && container) {
      const activeRoot = root
      await act(async () => {
        activeRoot.unmount()
      })
      container.remove()
    }
    document.body.replaceChildren()
    container = null
    root = null
  })

  // =========================================================================
  // SECTION 1: Extreme Mobile (320px, 360px, 375px, 414px)
  // =========================================================================
  describe('1. Extreme Mobile Viewport Stress (320px, 360px, 375px, 414px)', () => {
    const mobileViewports = [
      { width: 320, height: 568, name: 'iPhone SE (1st gen) 320px' },
      { width: 360, height: 640, name: 'Android Small 360px' },
      { width: 375, height: 667, name: 'iPhone SE (2nd gen) 375px' },
      { width: 414, height: 896, name: 'iPhone XR/Plus 414px' },
    ]

    for (const vp of mobileViewports) {
      it(`Subsystem 1 (Diff Workspace) on ${vp.name}: resists horizontal blowout with 150-char unbroken note type & template names`, async () => {
        window.innerWidth = vp.width
        window.innerHeight = vp.height
        window.dispatchEvent(new Event('resize'))

        const extremeItems: CardDiff[] = [
          {
            id: 'card_extreme_1',
            noteId: 'note_extreme_1',
            noteTypeId: 'nt_extreme_1',
            noteTypeName: UNBROKEN_SUPER_LONG_STRING,
            changeType: 'modified',
            primaryText: JAPANESE_EXTREME_STRING,
            secondaryText: UNBROKEN_SUPER_LONG_STRING,
            fieldDiffs: [
              {
                fieldName: 'Field_' + UNBROKEN_SUPER_LONG_STRING,
                before: 'Before_' + UNBROKEN_SUPER_LONG_STRING,
                after: 'After_' + UNBROKEN_SUPER_LONG_STRING,
                isConflict: true,
              },
            ],
            status: 'pending',
          },
        ]

        await act(async () => {
          root?.render(<HighVolumeDiffWorkspace items={extremeItems} />)
        })

        // Verify Toolbar Note Type Selector is safely truncated and max-w-full
        const select = container?.querySelector('select#note-type-filter') as HTMLSelectElement
        expect(select).not.toBeNull()
        expect(select.className).toContain('max-w-full')
        expect(select.className).toContain('truncate')

        // Verify Search wrapper is full-width on mobile
        const searchWrapper = container?.querySelector('.sm\\:w-72')
        expect(searchWrapper?.className).toContain('w-full')

        // Verify CardDiffItem text truncation
        const cardItem = container?.querySelector('[data-testid="card-diff-item-card_extreme_1"]')
        expect(cardItem).not.toBeNull()
        const primaryTextEl = cardItem?.querySelector('span.truncate')
        expect(primaryTextEl).not.toBeNull()
        expect(primaryTextEl?.getAttribute('title')).toContain('【完全網羅】JLPT N1')

        // Expand field diffs to verify break-words & break-all
        const toggleBtn = container?.querySelector('[data-testid="toggle-details-card_extreme_1"]') as HTMLButtonElement
        expect(toggleBtn).not.toBeNull()
        await act(async () => {
          toggleBtn.click()
        })

        const fieldDiffContainer = container?.querySelector('[data-testid="field-diffs-container-card_extreme_1"]')
        expect(fieldDiffContainer).not.toBeNull()
        const diffValues = fieldDiffContainer?.querySelectorAll('.break-words.break-all')
        expect(diffValues?.length).toBeGreaterThanOrEqual(2)
      })

      it(`Subsystem 2 (Deck Structural Dependencies) on ${vp.name}: truncates long names and wraps badges`, async () => {
        window.innerWidth = vp.width
        window.innerHeight = vp.height
        window.dispatchEvent(new Event('resize'))

        await act(async () => {
          root?.render(
            <DeckStructuralDependenciesCard
              deckTitle={UNBROKEN_SUPER_LONG_STRING}
              currentVersionLabel="v1.0.0-unbroken-version-tag"
              noteTypes={[
                {
                  note_type_id: 'nt_long',
                  note_type_name: UNBROKEN_SUPER_LONG_STRING,
                  note_count: 999,
                  pinned_version_label: 'v1.0.0',
                  latest_version_label: 'v2.0.0',
                  status: 'update_available',
                  has_draft_changes: false,
                  templates: [
                    {
                      template_id: 'tpl_long',
                      template_name: JAPANESE_EXTREME_STRING,
                      pinned_version_label: 'v1.0.0',
                      latest_version_label: 'v2.0.0',
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

        // Deck title must have break-words
        const deckTitle = container?.querySelector('span.break-words')
        expect(deckTitle).not.toBeNull()
        expect(deckTitle?.getAttribute('title')).toBe(UNBROKEN_SUPER_LONG_STRING)

        // Note type name must have truncate and max-w bounds
        const ntTitle = container?.querySelector('[data-testid="note-type-item-nt_long"] span.truncate')
        expect(ntTitle?.className).toContain('max-w-[200px]')

        // Template name must have truncate and max-w bounds
        const tplTitle = container?.querySelector('[data-testid="template-item-tpl_long"] span.truncate')
        expect(tplTitle?.className).toContain('max-w-[180px]')
      })

      it(`Subsystem 3 (Template Coherence Banner) on ${vp.name}: flex-col wraps action button cleanly`, async () => {
        window.innerWidth = vp.width
        window.innerHeight = vp.height
        window.dispatchEvent(new Event('resize'))

        await act(async () => {
          root?.render(
            <TemplateCoherenceBanner
              warnings={[
                {
                  template_id: 'tpl_warn_1',
                  template_name: UNBROKEN_SUPER_LONG_STRING,
                  warning_type: 'OUTDATED_PIN',
                  pinned_release: 'v1.0.0',
                  latest_release: 'v2.5.0-long-tag',
                  message: JAPANESE_EXTREME_STRING,
                  action_recommendation: UNBROKEN_SUPER_LONG_STRING,
                },
              ]}
              onAlignTemplatePin={vi.fn()}
            />
          )
        })

        // Warning item must use flex-col on mobile to stack gracefully
        const warningItem = container?.querySelector('[data-testid="coherence-warning-tpl_warn_1"]') as HTMLDivElement
        expect(warningItem.className).toContain('flex-col')
        expect(warningItem.className).toContain('sm:flex-row')

        // Align button must be full-width on mobile with whitespace-normal
        const alignBtn = container?.querySelector('[data-testid="align-template-pin-tpl_warn_1"]') as HTMLButtonElement
        expect(alignBtn.className).toContain('w-full')
        expect(alignBtn.className).toContain('whitespace-normal')
      })

      it(`Subsystem 4 (Cascading Sync Modal) on ${vp.name}: flex-wrap prevents stats overflow`, async () => {
        window.innerWidth = vp.width
        window.innerHeight = vp.height
        window.dispatchEvent(new Event('resize'))

        await act(async () => {
          root?.render(
            <CascadingSyncSummaryModal
              open={true}
              onOpenChange={vi.fn()}
              summary={{
                deck_id: 'deck_adv_1',
                deck_title: UNBROKEN_SUPER_LONG_STRING,
                version_label: 'v2.0',
                from_version_label: 'v1.0',
                cards_updated: 99999,
                cards_added: 33333,
                cards_modified: 33333,
                cards_removed: 33333,
                progress_preserved_count: 88888,
                note_types_updated: [
                  { id: 'nt_1', name: UNBROKEN_SUPER_LONG_STRING, version: 'v2.0' },
                ],
                templates_updated: [
                  { id: 'tpl_1', name: JAPANESE_EXTREME_STRING, from_version: 'v1.0', to_version: 'v2.0' },
                ],
              }}
            />
          )
        })

        // Deck title has break-words
        const deckTitle = document.body.querySelector('span.break-words')
        expect(deckTitle).not.toBeNull()

        // Card sync stat container must flex-wrap
        const statRow = document.body.querySelector('[data-testid="cards-sync-stat"]') as HTMLDivElement
        expect(statRow.className).toContain('flex-wrap')
        expect(statRow.className).toContain('gap-1')

        // Note type name has truncate max-w-[200px]
        const ntName = document.body.querySelector('[data-testid="note-types-sync-list"] span.truncate')
        expect(ntName?.className).toContain('max-w-[200px]')
      })
    }
  })

  // =========================================================================
  // SECTION 2: Touch Targets Audit on Mobile
  // =========================================================================
  describe('2. Mobile Touch Targets Audit (>= 44x44px for Checkbox, >= 38px for Action Buttons)', () => {
    it('verifies CardDiffItem checkbox has hit-box padding meeting >= 44x44px', async () => {
      const item: CardDiff = {
        id: 'card_touch_1',
        noteId: 'note_1',
        noteTypeId: 'nt_1',
        noteTypeName: 'Vocabulary',
        changeType: 'added',
        primaryText: 'Sample Item',
        status: 'pending',
      }

      await act(async () => {
        root?.render(<CardDiffItem item={item} isSelected={false} onToggle={vi.fn()} />)
      })

      const checkboxBtn = container?.querySelector('[data-testid="card-checkbox-card_touch_1"]') as HTMLButtonElement
      expect(checkboxBtn).not.toBeNull()

      // Empirical check: min-h-[44px] and min-w-[44px] with -m-2 p-2 touch margin expansion
      expect(checkboxBtn.className).toContain('min-h-[44px]')
      expect(checkboxBtn.className).toContain('min-w-[44px]')
      expect(checkboxBtn.className).toContain('p-2')
      expect(checkboxBtn.className).toContain('-m-2')
    })

    it('verifies DiffFilterToolbar filter pills have mobile touch target >= 38px', async () => {
      await act(async () => {
        root?.render(
          <DiffFilterToolbar
            filters={{ changeType: 'all', noteTypeId: 'all', searchQuery: '' }}
            summary={{ totalNotes: 10, addedCount: 3, modifiedCount: 3, removedCount: 2, conflictCount: 2 }}
            groups={[]}
            visibleCount={10}
            selectedCount={0}
            onFiltersChange={vi.fn()}
            onToggleSelectAllVisible={vi.fn()}
          />
        )
      })

      const pills = container?.querySelectorAll('button[aria-pressed]')
      expect(pills?.length).toBeGreaterThanOrEqual(4)

      pills?.forEach((pill) => {
        const btn = pill as HTMLButtonElement
        expect(btn.className).toContain('min-h-[38px]')
      })
    })

    it('verifies BatchActionBar action buttons have mobile touch target >= 38px', async () => {
      await act(async () => {
        root?.render(
          <BatchActionBar
            selectedCount={5}
            totalCount={20}
            onApprove={vi.fn()}
            onReject={vi.fn()}
            onClear={vi.fn()}
          />
        )
      })

      const approveBtn = container?.querySelector('[data-testid="batch-approve-btn"]') as HTMLButtonElement
      const rejectBtn = container?.querySelector('[data-testid="batch-reject-btn"]') as HTMLButtonElement
      const clearBtn = container?.querySelector('[data-testid="batch-clear-btn"]') as HTMLButtonElement

      expect(approveBtn.className).toContain('min-h-[38px]')
      expect(rejectBtn.className).toContain('min-h-[38px]')
      expect(clearBtn.className).toContain('min-h-[38px]')
    })

    it('verifies TemplateCoherenceBanner action button has touch target >= 36px', async () => {
      await act(async () => {
        root?.render(
          <TemplateCoherenceBanner
            warnings={[
              {
                template_id: 't1',
                template_name: 'Template 1',
                warning_type: 'OUTDATED_PIN',
                latest_release: 'v2.0',
                message: 'Warning',
              },
            ]}
            onAlignTemplatePin={vi.fn()}
          />
        )
      })

      const alignBtn = container?.querySelector('[data-testid="align-template-pin-t1"]') as HTMLButtonElement
      expect(alignBtn.className).toContain('min-h-[36px]')
    })

    it('verifies CascadingSyncSummaryModal action buttons have mobile height h-9 (36px)', async () => {
      await act(async () => {
        root?.render(
          <CascadingSyncSummaryModal
            open={true}
            onOpenChange={vi.fn()}
            summary={{
              deck_id: 'd1',
              deck_title: 'Deck 1',
              version_label: 'v2.0',
              progress_preserved_count: 100,
              note_types_updated: [],
              templates_updated: [],
            }}
          />
        )
      })

      const closeBtn = document.body.querySelector('[data-testid="close-modal-btn"]') as HTMLButtonElement
      const startStudyBtn = document.body.querySelector('[data-testid="start-study-btn"]') as HTMLButtonElement

      expect(closeBtn.className).toContain('h-9')
      expect(startStudyBtn.className).toContain('h-9')
    })
  })

  // =========================================================================
  // SECTION 3: Office Laptop (1366x768) Viewport Budget & Scroll Trap
  // =========================================================================
  describe('3. Office Laptop (1366x768) Viewport Budget & Scroll Isolation', () => {
    it('verifies HighVolumeDiffWorkspace containerHeight formula on 1366x768', async () => {
      window.innerWidth = 1366
      window.innerHeight = 768
      window.dispatchEvent(new Event('resize'))

      const items: CardDiff[] = Array.from({ length: 30 }, (_, i) => ({
        id: `card_${i}`,
        noteId: `note_${i}`,
        noteTypeId: 'nt_1',
        noteTypeName: 'Vocabulary',
        changeType: 'modified',
        primaryText: `Item ${i}`,
        status: 'pending',
      }))

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]'
      ) as HTMLDivElement

      expect(scrollContainer).not.toBeNull()

      // 1. Verify default style.maxHeight formula
      expect(scrollContainer.style.maxHeight).toContain('380px')
      expect(scrollContainer.style.maxHeight).toContain('calc(100dvh - 280px)')

      // 2. Container class contains responsive max-h bounds
      expect(scrollContainer.className).toContain('max-h-[58vh]')
      expect(scrollContainer.className).toContain('sm:max-h-[65vh]')
      expect(scrollContainer.className).toContain('lg:max-h-[calc(100dvh-20rem)]')

      // 3. Selection of item triggers BatchActionBar inside the workspace
      const checkbox = container?.querySelector('[data-testid="card-checkbox-card_0"]') as HTMLButtonElement
      await act(async () => {
        checkbox.click()
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]') as HTMLDivElement
      expect(batchBar).not.toBeNull()
      expect(batchBar.className).toContain('sticky')
      expect(batchBar.className).toContain('bottom-3')
    })

    it('verifies scroll container does NOT use overscroll-contain or overflow-hidden that traps outer page scrolling', async () => {
      const items: CardDiff[] = Array.from({ length: 10 }, (_, i) => ({
        id: `card_${i}`,
        noteId: `note_${i}`,
        noteTypeId: 'nt_1',
        noteTypeName: 'Vocabulary',
        changeType: 'added',
        primaryText: `Item ${i}`,
        status: 'pending',
      }))

      await act(async () => {
        root?.render(<HighVolumeDiffWorkspace items={items} />)
      })

      const scrollContainer = container?.querySelector(
        '[data-testid="virtualized-diff-container"]'
      ) as HTMLDivElement

      // Must have overflow-y-auto to allow standard scrolling
      expect(scrollContainer.className).toContain('overflow-y-auto')

      // Must NOT contain overscroll-contain (which traps wheel events)
      expect(scrollContainer.className).not.toContain('overscroll-contain')
      expect(scrollContainer.className).not.toContain('overscroll-none')
    })
  })

  // =========================================================================
  // SECTION 4: Desktop 2K/4K Containment
  // =========================================================================
  describe('4. Desktop 2K & 4K Ultra-Wide Containment', () => {
    it('verifies HighVolumeDiffWorkspace enforces max-w-7xl mx-auto on 2560x1440 and 3840x2160', async () => {
      const desktopViewports = [
        { width: 2560, height: 1440, name: '2K QHD' },
        { width: 3840, height: 2160, name: '4K UHD' },
      ]

      for (const vp of desktopViewports) {
        window.innerWidth = vp.width
        window.innerHeight = vp.height
        window.dispatchEvent(new Event('resize'))

        const items: CardDiff[] = Array.from({ length: 5 }, (_, i) => ({
          id: `card_${i}`,
          noteId: `note_${i}`,
          noteTypeId: 'nt_1',
          noteTypeName: 'Vocabulary',
          changeType: 'added',
          primaryText: `Item ${i}`,
          status: 'pending',
        }))

        await act(async () => {
          root?.render(<HighVolumeDiffWorkspace items={items} />)
        })

        const workspace = container?.querySelector('[data-testid="high-volume-diff-workspace"]') as HTMLDivElement
        expect(workspace).not.toBeNull()

        // Verify max-w-7xl (80rem = 1280px) and mx-auto (centered)
        expect(workspace.className).toContain('max-w-7xl')
        expect(workspace.className).toContain('mx-auto')
        expect(workspace.className).toContain('w-full')
      }
    })
  })

  // =========================================================================
  // SECTION 5: Mobile Space-Saving Ergonomics & Label Truncation (320px)
  // =========================================================================
  describe('5. Mobile Ergonomics & Adaptive Label Hiding (320px)', () => {
    it('verifies BatchActionBar hides percentage and label text on 320px mobile to conserve space', async () => {
      window.innerWidth = 320
      window.innerHeight = 568
      window.dispatchEvent(new Event('resize'))

      await act(async () => {
        root?.render(
          <BatchActionBar
            selectedCount={99999}
            totalCount={99999}
            onApprove={vi.fn()}
            onReject={vi.fn()}
            onClear={vi.fn()}
          />
        )
      })

      const batchBar = container?.querySelector('[data-testid="batch-action-bar"]') as HTMLDivElement
      expect(batchBar).not.toBeNull()

      // 1. Percentage badge has hidden sm:inline-flex
      const percentBadge = batchBar.querySelector('.font-mono.ml-1')
      expect(percentBadge?.className).toContain('hidden')
      expect(percentBadge?.className).toContain('sm:inline-flex')

      // 2. Clear button text has hidden sm:inline
      const clearSpan = batchBar.querySelector('[data-testid="batch-clear-btn"] span')
      expect(clearSpan?.className).toContain('hidden')
      expect(clearSpan?.className).toContain('sm:inline')

      // 3. Actions row uses w-full sm:w-auto to wrap below counter on 320px
      const actionsRow = batchBar.querySelector('.w-full.sm\\:w-auto')
      expect(actionsRow).not.toBeNull()
    })

    it('verifies NoteTypeDiffGroup hides action button text on 320px mobile to prevent header blowout', async () => {
      window.innerWidth = 320
      window.innerHeight = 568
      window.dispatchEvent(new Event('resize'))

      await act(async () => {
        root?.render(
          <NoteTypeDiffGroup
            group={{
              noteTypeId: 'nt_1',
              noteTypeName: 'Kanji N1',
              totalCount: 50,
              addedCount: 20,
              modifiedCount: 15,
              removedCount: 10,
              conflictCount: 5,
              items: [],
            }}
            isCollapsed={false}
            allSelected={false}
            someSelected={false}
            onToggleCollapse={vi.fn()}
            onToggleSelectGroup={vi.fn()}
            onApproveGroup={vi.fn()}
            onRejectGroup={vi.fn()}
          />
        )
      })

      const approveGroupBtn = container?.querySelector('[data-testid="approve-group-nt_1"]')
      const approveText = approveGroupBtn?.querySelector('span')
      expect(approveText?.className).toContain('hidden')
      expect(approveText?.className).toContain('sm:inline')

      const rejectGroupBtn = container?.querySelector('[data-testid="reject-group-nt_1"]')
      const rejectText = rejectGroupBtn?.querySelector('span')
      expect(rejectText?.className).toContain('hidden')
      expect(rejectText?.className).toContain('sm:inline')
    })
  })
})

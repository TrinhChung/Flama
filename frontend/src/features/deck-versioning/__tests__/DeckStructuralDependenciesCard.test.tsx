// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DeckStructuralDependenciesCard } from '../components/DeckStructuralDependenciesCard'
import type { NoteTypeDependency } from '../model/types'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('DeckStructuralDependenciesCard', () => {
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
  })

  const mockNoteTypes: NoteTypeDependency[] = [
    {
      note_type_id: 'nt_vocab_n3',
      note_type_name: 'Từ vựng N3 Chuẩn',
      note_count: 1420,
      pinned_version_label: 'v1.0.0',
      latest_version_label: 'v1.1.0',
      status: 'update_available',
      has_draft_changes: false,
      templates: [
        {
          template_id: 'tmpl_recognition',
          template_name: 'Thẻ Từ vựng - Nhận diện',
          occurrence_key: 'occ_main',
          pinned_version_label: 'v2.0.0',
          latest_version_label: 'v2.1.0',
          status: 'update_available',
          has_newer_release: true,
          has_uncommitted_draft: false,
        },
        {
          template_id: 'tmpl_production',
          template_name: 'Thẻ Từ vựng - Tự viết',
          occurrence_key: 'occ_prod',
          pinned_version_label: 'v1.0.0',
          latest_version_label: 'v1.0.0',
          status: 'synced',
          has_newer_release: false,
          has_uncommitted_draft: false,
        },
      ],
    },
    {
      note_type_id: 'nt_kanji_n3',
      note_type_name: 'Hán tự N3',
      note_count: 350,
      pinned_version_label: 'v1.2.0',
      latest_version_label: 'v1.2.0',
      status: 'draft_changes',
      has_draft_changes: true,
      templates: [
        {
          template_id: 'tmpl_kanji_card',
          template_name: 'Thẻ Hán tự',
          occurrence_key: 'occ_kanji',
          pinned_version_label: 'v1.0.0',
          latest_version_label: 'v1.0.0',
          status: 'draft_changes',
          has_newer_release: false,
          has_uncommitted_draft: true,
        },
      ],
    },
  ]

  it('renders Note Types and Card Templates with titles and versions', async () => {
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3 Kanji & Vocab"
          currentVersionLabel="v1.2.0"
          noteTypes={mockNoteTypes}
        />
      )
    })

    // Header info
    expect(container.textContent).toContain('Soumatome N3 Kanji & Vocab')
    expect(container.textContent).toContain('v1.2.0')
    expect(container.textContent).toContain('Phụ thuộc Cấu trúc (Note Types & Templates)')

    // Note types
    expect(container.textContent).toContain('Từ vựng N3 Chuẩn')
    expect(container.textContent).toContain('(1420 thẻ)')
    expect(container.textContent).toContain('pin: v1.0.0')
    expect(container.textContent).toContain('Mới nhất: v1.1.0')

    expect(container.textContent).toContain('Hán tự N3')
    expect(container.textContent).toContain('(350 thẻ)')
    expect(container.textContent).toContain('pin: v1.2.0')

    // Attached templates
    expect(container.textContent).toContain('Thẻ Từ vựng - Nhận diện')
    expect(container.textContent).toContain('[occ_main]')
    expect(container.textContent).toContain('pin: v2.0.0')

    expect(container.textContent).toContain('Thẻ Từ vựng - Tự viết')
    expect(container.textContent).toContain('[occ_prod]')

    expect(container.textContent).toContain('Thẻ Hán tự')
  })

  it('displays correct status badges (Synced, Update Available, Draft Changes)', async () => {
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3"
          currentVersionLabel="v1.0.0"
          noteTypes={mockNoteTypes}
        />
      )
    })

    const badges = Array.from(container.querySelectorAll('[data-status]'))
    const statuses = badges.map((b) => b.getAttribute('data-status'))

    // Should contain update_available, synced, and draft_changes
    expect(statuses).toContain('update_available')
    expect(statuses).toContain('synced')
    expect(statuses).toContain('draft_changes')

    // Text labels
    expect(container.textContent).toContain('Synced')
    expect(container.textContent).toContain('Update Available')
    expect(container.textContent).toContain('Draft Changes')
  })

  it('calls navigation callbacks when CTA buttons are clicked', async () => {
    const onNavigateToNoteType = vi.fn()
    const onNavigateToTemplate = vi.fn()

    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3"
          currentVersionLabel="v1.0.0"
          noteTypes={mockNoteTypes}
          onNavigateToNoteType={onNavigateToNoteType}
          onNavigateToTemplate={onNavigateToTemplate}
        />
      )
    })

    // Click Note Type CTA
    const ntButton = container.querySelector<HTMLButtonElement>(
      '[data-testid="navigate-note-type-nt_vocab_n3"]'
    )
    expect(ntButton).not.toBeNull()
    await act(async () => {
      ntButton?.click()
    })
    expect(onNavigateToNoteType).toHaveBeenCalledWith('nt_vocab_n3')

    // Click Template CTA
    const tplButton = container.querySelector<HTMLButtonElement>(
      '[data-testid="navigate-template-tmpl_recognition"]'
    )
    expect(tplButton).not.toBeNull()
    await act(async () => {
      tplButton?.click()
    })
    expect(onNavigateToTemplate).toHaveBeenCalledWith('tmpl_recognition')
  })

  it('strictly does not render raw code, HTML/CSS or diff snippets', async () => {
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3"
          currentVersionLabel="v1.0.0"
          noteTypes={mockNoteTypes}
        />
      )
    })

    // Verify absence of raw code elements
    expect(container.querySelectorAll('pre').length).toBe(0)
    expect(container.querySelectorAll('code').length).toBe(0)

    // Verify no raw mustache, JSON diffs or HTML markup leak into text content
    expect(container.textContent).not.toContain('{{')
    expect(container.textContent).not.toContain('}}')
    expect(container.textContent).not.toContain('<div')
    expect(container.textContent).not.toContain('diff_match_patch')
    expect(container.textContent).not.toContain('"change_type"')
  })

  it('renders loading state when isLoading is true', async () => {
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3"
          noteTypes={[]}
          isLoading={true}
        />
      )
    })

    expect(container.textContent).toContain('Đang kiểm tra phụ thuộc cấu trúc…')
  })

  it('renders empty message when noteTypes list is empty', async () => {
    await act(async () => {
      root.render(
        <DeckStructuralDependenciesCard
          deckTitle="Soumatome N3"
          noteTypes={[]}
          isLoading={false}
        />
      )
    })

    expect(container.textContent).toContain('Không có Loại thẻ nào trong bộ thẻ này.')
  })
})

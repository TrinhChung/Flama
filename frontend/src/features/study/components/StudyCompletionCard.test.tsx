// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StudyCompletionCard } from './StudyCompletionCard'
import type { PersistedStudySession } from '../session/sessionStore'
import type { StudySessionCommitReceipt } from '../types'

vi.mock('@/features/worksheets/components/LazyDeckWorksheetModal', () => ({
  LazyDeckWorksheetModal: vi.fn(({ open, deckId, deckName }: any) =>
    open ? (
      <div data-testid="deck-worksheet-modal" data-deck-id={deckId} data-deck-name={deckName}>
        Mock Worksheet Modal
      </div>
    ) : null,
  ),
}))

let root: Root | null = null
let container: HTMLDivElement | null = null

function render(ui: React.ReactNode) {
  return (
    <MemoryRouter>
      {ui}
    </MemoryRouter>
  )
}

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  if (root) await act(async () => root?.unmount())
  root = null
  container?.remove()
  container = null
  document.body.replaceChildren()
})

function createMockSession(overrides?: Partial<PersistedStudySession>): PersistedStudySession {
  return {
    scope_key: 'user:1:deck:10',
    snapshot: {
      schema_version: 'study-session.v2',
      session_id: 'session-123',
      session_token: 'tok-123',
      user_id: 1,
      scope: { type: 'deck', id: '10', name: 'JLPT N3 Kanji' },
      server_now_utc: '2026-09-05T00:00:00Z',
      expires_at: '2026-09-05T01:00:00Z',
      timezone: 'UTC',
      day_boundary_hour_local: 4,
      learn_ahead_seconds: 1200,
      snapshot_hash: 'hash-123',
      scheduler_algorithm: 'legacy-anki',
      algorithm_version: '1.0.0',
      queue_contract_version: '1',
      compositions: {},
      cards: [],
      templates: {},
      contents: {},
      policies: {},
    },
    events: [],
    touched_card_ids: [],
    opened_client_at_ms: Date.now() - 300_000,
    status: 'active',
    commit_id: null,
    commit_reason: null,
    resume_after_commit: false,
    updated_at_ms: Date.now(),
    ...overrides,
  }
}

describe('StudyCompletionCard', () => {
  it('displays accurate total count and duration combining past syncs with current batch', async () => {
    const onCommit = vi.fn()
    // Session had 50 cards synced previously during rollover (total duration 600,000 ms = 10 mins)
    // and 2 cards answered in the current batch (total duration 120,000 ms = 2 mins)
    const session = createMockSession({
      accumulated_stats: {
        total_reviews: 50,
        total_duration_ms: 600_000,
        again_count: 5,
        hard_count: 5,
        good_count: 30,
        easy_count: 10,
      },
      events: [
        {
          event_id: 'ev-1',
          sequence: 1,
          card_id: 'card-1',
          rating: 'good',
          action_key: 'review.good',
          trigger_key: 'scheduler.review.good',
          trigger_contract_version: '1',
          policy_key: 'pol-1',
          scheduler_offset_ms: 1000,
          duration_ms: 60_000,
        },
        {
          event_id: 'ev-2',
          sequence: 2,
          card_id: 'card-2',
          rating: 'easy',
          action_key: 'review.easy',
          trigger_key: 'scheduler.review.easy',
          trigger_contract_version: '1',
          policy_key: 'pol-1',
          scheduler_offset_ms: 2000,
          duration_ms: 60_000,
        },
      ],
    })

    await act(async () => {
      root?.render(
        render(
          <StudyCompletionCard
            deckName="JLPT N3 Kanji"
            deckId="10"
            session={session}
            receipt={null}
            counts={{ new: 0, learning: 0, due: 0 }}
            isBusy={false}
            onCommit={onCommit}
          />,
        ),
      )
    })

    // Total cards should be 50 from previous sync + 2 from current batch = 52 cards!
    expect(container?.textContent).toContain('52 thẻ')
    // Total time should be 10 mins (600s) + 2 mins (120s) = 12 phút
    expect(container?.textContent).toContain('12 phút')
    // Rating breakdown should show accumulated + current
    expect(container?.textContent).toContain('Quên')
    expect(container?.textContent).toContain('Khó')
    expect(container?.textContent).toContain('Tốt')
    expect(container?.textContent).toContain('Dễ')
    // Button to commit and sync
    const syncButton = Array.from(container?.querySelectorAll('button') || []).find((b) =>
      b.textContent?.includes('Kết thúc & Đồng bộ phiên'),
    )
    expect(syncButton).toBeDefined()
    await act(async () => {
      syncButton?.click()
    })
    expect(onCommit).toHaveBeenCalledTimes(1)
  })

  it('displays full session counts upon receipt commit', async () => {
    const session = createMockSession({
      accumulated_stats: {
        total_reviews: 65,
        total_duration_ms: 780_000, // 13 minutes
        again_count: 5,
        hard_count: 10,
        good_count: 40,
        easy_count: 10,
      },
    })

    const receipt: StudySessionCommitReceipt = {
      schema_version: 'study-commit-receipt.v1',
      success: true,
      session_id: 'session-123',
      commit_id: 'commit-456',
      commit_reason: 'manual_exit',
      applied_event_count: 15, // last batch had 15, but entire session had 65!
      updated_cards: [],
      rating_counts: { again: 1, hard: 2, good: 10, easy: 2 },
      committed_at: '2026-09-05T00:15:00Z',
    }

    await act(async () => {
      root?.render(
        render(
          <StudyCompletionCard
            deckName="JLPT N3 Kanji"
            deckId="10"
            session={session}
            receipt={receipt}
            counts={{ new: 0, learning: 0, due: 0 }}
            isBusy={false}
            onCommit={vi.fn()}
          />,
        ),
      )
    })

    // Header should acknowledge all 65 cards
    expect(container?.textContent).toContain('Đã đồng bộ phiên học')
    expect(container?.textContent).toContain('65 lượt trả lời thẻ')
    expect(container?.textContent).toContain('65 thẻ')
    expect(container?.textContent).toContain('13 phút')

    const links = Array.from(container?.querySelectorAll('a') || [])
    const dashboardLink = links.find((a) => a.textContent?.includes('Về Dashboard'))
    expect(dashboardLink?.getAttribute('href')).toBe('/dashboard')
  })

  it('renders worksheet button and opens DeckWorksheetModal when clicked', async () => {
    const session = createMockSession({
      accumulated_stats: {
        total_reviews: 10,
        total_duration_ms: 120_000,
        again_count: 1,
        hard_count: 1,
        good_count: 6,
        easy_count: 2,
      },
    })

    const receipt: StudySessionCommitReceipt = {
      schema_version: 'study-commit-receipt.v1',
      success: true,
      session_id: 'session-123',
      commit_id: 'commit-456',
      commit_reason: 'manual_exit',
      applied_event_count: 10,
      updated_cards: [],
      rating_counts: { again: 1, hard: 1, good: 6, easy: 2 },
      committed_at: '2026-09-05T00:15:00Z',
    }

    await act(async () => {
      root?.render(
        render(
          <StudyCompletionCard
            deckName="JLPT N3 Kanji"
            deckId="10"
            session={session}
            receipt={receipt}
            counts={{ new: 0, learning: 0, due: 0 }}
            isBusy={false}
            onCommit={vi.fn()}
          />,
        ),
      )
    })

    const worksheetBtn = Array.from(container?.querySelectorAll('button') || []).find((b) =>
      b.textContent?.includes('Tạo Worksheet cho deck'),
    )
    expect(worksheetBtn).toBeDefined()

    // Initially modal should not be rendered
    expect(container?.querySelector('[data-testid="deck-worksheet-modal"]')).toBeNull()

    // Click worksheet button
    await act(async () => {
      worksheetBtn?.click()
    })

    // Now modal should be open with correct deckId and deckName
    const modalEl = container?.querySelector('[data-testid="deck-worksheet-modal"]')
    expect(modalEl).not.toBeNull()
    expect(modalEl?.getAttribute('data-deck-id')).toBe('10')
    expect(modalEl?.getAttribute('data-deck-name')).toBe('JLPT N3 Kanji')
  })
})

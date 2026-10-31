// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { DeckCard, type DeckCardItem } from '@/entities/marketplace-deck'

describe('DeckCard Component', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    if (root && container) {
      const activeRoot = root
      act(() => {
        activeRoot.unmount()
      })
      container.remove()
    }
    container = null
    root = null
  })

  it('renders marketplace variant card with title, author and price', () => {
    const item: DeckCardItem = {
      id: 'deck-1',
      title: 'Minna no Nihongo N5 Vocabulary',
      primary_category: 'Tiếng Nhật',
      price_display: 'Miễn phí',
      pricing_mode: 'free',
      rating_avg: 4.8,
      rating_count: 120,
      install_count: 530,
      note_count: 500,
      author: {
        username: 'sensei_tanaka',
        account_name: 'Tanaka Sensei',
      },
    }

    act(() => {
      root?.render(
        <BrowserRouter>
          <DeckCard item={item} variant="marketplace" />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).toContain('Minna no Nihongo N5 Vocabulary')
    expect(container?.textContent).toContain('Tanaka Sensei')
    expect(container?.textContent).toContain('Tiếng Nhật')
    expect(container?.textContent).toContain('Miễn phí')
    expect(container?.textContent).toContain('4.8')
    expect(container?.textContent).toContain('500 từ')
    expect(container?.textContent).toContain('Xem chi tiết')
  })

  it('renders course deck badges and action button when distribution_mode is course_key', () => {
    const item: DeckCardItem = {
      id: 'deck-course-1',
      title: 'N2 JLPT Master Course Deck',
      primary_category: 'Tiếng Nhật',
      distribution_mode: 'course_key',
      requires_access_key: true,
      price_display: 'Mã khóa học',
      rating_avg: 5.0,
      note_count: 850,
      author: {
        username: 'academy_pro',
        account_name: 'Nihongo Academy',
      },
    }

    act(() => {
      root?.render(
        <BrowserRouter>
          <DeckCard item={item} variant="marketplace" />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).toContain('N2 JLPT Master Course Deck')
    expect(container?.textContent).toContain('Khóa học')
    expect(container?.textContent).toContain('Mã khóa học')
    expect(container?.textContent).toContain('Xem khóa học & Nhập mã')
  })

  it('renders installed variant card with install_bucket and study button', () => {
    const item: DeckCardItem = {
      id: 'deck-installed-1',
      title: 'Kanji Look and Learn N4',
      primary_category: 'Tiếng Nhật',
      install_bucket: 'using_now',
      auto_update_enabled: true,
      installed_deck_id: 42,
      deck_install_id: 'install-42',
      note_count: 320,
      author: {
        username: 'kanji_master',
      },
    }

    act(() => {
      root?.render(
        <BrowserRouter>
          <DeckCard item={item} variant="installed" />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).toContain('Kanji Look and Learn N4')
    expect(container?.textContent).toContain('Đang sử dụng')
    expect(container?.textContent).not.toContain('Auto')
    expect(container?.textContent).toContain('Học ngay')
  })

  it('ignores obsolete update conflicts and keeps contributions available', () => {
    const item: DeckCardItem = {
      id: 'deck-conflict-1',
      title: 'Soumatome N3 Grammar',
      install_bucket: 'installed',
      deck_install_id: 'install-100',
      last_sync_status: 'conflict',
      pending_conflict_count: 3,
      installed_deck_id: 100,
    }

    act(() => {
      root?.render(
        <BrowserRouter>
          <DeckCard item={item} variant="installed" />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).not.toContain('xung đột')
    expect(container?.querySelector('a[href*="/updates/"]')).toBeNull()
    expect(container?.querySelector('a[href$="/change-request"]')).not.toBeNull()
  })

  it('renders student discount badge when student_discount_applied is true', () => {
    const item: DeckCardItem = {
      id: 'deck-student-1',
      title: 'TOEIC 900+ Master Vocab',
      primary_category: 'Tiếng Anh',
      pricing_mode: 'paid',
      price_display: '99.000 đ',
      has_student_offer: true,
      student_discount_applied: true,
      effective_price_display: '69.000 đ',
      author: {
        username: 'toeic_pro',
      },
    }

    act(() => {
      root?.render(
        <BrowserRouter>
          <DeckCard item={item} variant="marketplace" />
        </BrowserRouter>,
      )
    })

    expect(container?.textContent).toContain('TOEIC 900+ Master Vocab')
    expect(container?.textContent).toContain('99.000 đ')
    expect(container?.textContent).toContain('69.000 đ')
  })
})

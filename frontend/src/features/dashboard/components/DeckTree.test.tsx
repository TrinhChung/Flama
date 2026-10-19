// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeckNode } from '../types'
import { DeckTree } from './DeckTree'

const deck: DeckNode = {
  id: 42,
  parent_id: null,
  name: 'N3 Vocabulary',
  depth: 0,
  study_url: '/study?deck_id=42',
  counts: { new: 10, learning: 2, due: 3 },
  move: { alias: 'deck-42', token: 'token', parent_alias: null, parent_token: null },
  actions: {
    rename: '/api/decks/42',
    move: '/api/decks/42',
    delete: '/api/decks/42',
    reset: '/api/decks/42/progress-reset',
    share: '/marketplace/decks',
  },
  children: [],
}

describe('DeckTree interactions', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('selects and activates a deck on double click', () => {
    const onSelect = vi.fn()
    const onActivate = vi.fn()

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            onSelect={onSelect}
            onActivate={onActivate}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const row = container.querySelector<HTMLElement>('[data-node-id="42"]')
    expect(row).not.toBeNull()
    act(() => {
      row?.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))
    })

    expect(onSelect).toHaveBeenCalledWith(deck)
    expect(onActivate).toHaveBeenCalledWith(deck)
  })

  it('activates the focused deck with Enter', () => {
    const onActivate = vi.fn()

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            onActivate={onActivate}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const row = container.querySelector<HTMLElement>('[data-node-id="42"]')
    act(() => {
      row?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })

    expect(onActivate).toHaveBeenCalledWith(deck)
  })

  it('does not permanently suppress activation when pointer-up races drag state', () => {
    vi.useFakeTimers()
    const onActivate = vi.fn()
    const elementFromPointDescriptor = Object.getOwnPropertyDescriptor(document, 'elementFromPoint')

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            onActivate={onActivate}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const row = container.querySelector<HTMLElement>('[data-node-id="42"]')
    Object.defineProperty(document, 'elementFromPoint', {
      configurable: true,
      value: () => row,
    })
    act(() => {
      row?.dispatchEvent(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 10, clientY: 10 }))
      window.dispatchEvent(new MouseEvent('pointermove', { bubbles: true, clientX: 20, clientY: 10 }))
      window.dispatchEvent(new MouseEvent('pointerup', { bubbles: true, clientX: 20, clientY: 10 }))
      vi.advanceTimersByTime(301)
      row?.dispatchEvent(new MouseEvent('dblclick', { bubbles: true }))
    })

    expect(onActivate).toHaveBeenCalledWith(deck)
    if (elementFromPointDescriptor) {
      Object.defineProperty(document, 'elementFromPoint', elementFromPointDescriptor)
    } else {
      delete (document as Partial<Document>).elementFromPoint
    }
    vi.useRealTimers()
  })

  it('renders settings menu with import option for deck', () => {
    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const settingsButton = container.querySelector<HTMLButtonElement>('.deck-settings-btn')
    expect(settingsButton).not.toBeNull()
    act(() => {
      settingsButton?.focus()
      settingsButton?.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', bubbles: true, cancelable: true }),
      )
    })

    expect(document.body.textContent).toContain('Import thẻ')
  })

  it('keeps child decks collapsed by default and persists expanded state to localStorage on toggle', () => {
    localStorage.clear()

    const childDeck: DeckNode = {
      ...deck,
      id: 99,
      parent_id: 42,
      name: 'N3 Grammar Child',
      depth: 1,
      children: [],
    }

    const parentDeck: DeckNode = {
      ...deck,
      id: 42,
      name: 'N3 Parent',
      children: [childDeck],
    }

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[parentDeck]}
            adminMode={false}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    // On initial load, child deck should be collapsed (not in DOM)
    expect(container.querySelector('[data-node-id="99"]')).toBeNull()

    const toggleButton = container.querySelector<HTMLButtonElement>('.tree-toggle')
    expect(toggleButton).not.toBeNull()
    expect(toggleButton?.getAttribute('aria-expanded')).toBe('false')

    // Click to expand
    act(() => {
      toggleButton?.click()
    })

    expect(container.querySelector('[data-node-id="99"]')).not.toBeNull()
    expect(toggleButton?.getAttribute('aria-expanded')).toBe('true')
    expect(localStorage.getItem('flama_dashboard_expanded_deck_ids')).toContain('42')

    // Click again to collapse
    act(() => {
      toggleButton?.click()
    })

    expect(container.querySelector('[data-node-id="99"]')).toBeNull()
    expect(toggleButton?.getAttribute('aria-expanded')).toBe('false')
  })

  it('restores expanded state from localStorage on load', () => {
    localStorage.setItem('flama_dashboard_expanded_deck_ids', JSON.stringify([42]))

    const childDeck: DeckNode = {
      ...deck,
      id: 99,
      parent_id: 42,
      name: 'N3 Grammar Child',
      depth: 1,
      children: [],
    }

    const parentDeck: DeckNode = {
      ...deck,
      id: 42,
      name: 'N3 Parent',
      children: [childDeck],
    }

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[parentDeck]}
            adminMode={false}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    // Child deck should be restored as expanded
    expect(container.querySelector('[data-node-id="99"]')).not.toBeNull()
    const toggleButton = container.querySelector<HTMLButtonElement>('.tree-toggle')
    expect(toggleButton?.getAttribute('aria-expanded')).toBe('true')
  })

  it('does not trigger deck drag or move when swiping/scrolling on touch before long-press delay', () => {
    vi.useFakeTimers()
    const onMoveDeck = vi.fn().mockResolvedValue(undefined)
    const targetDeck: DeckNode = {
      ...deck,
      id: 77,
      name: 'N2 Vocabulary',
    }
    const elementFromPointDescriptor = Object.getOwnPropertyDescriptor(document, 'elementFromPoint')

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck, targetDeck]}
            adminMode={false}
            onAction={vi.fn()}
            onMoveDeck={onMoveDeck}
          />
        </MemoryRouter>,
      )
    })

    const sourceRow = container.querySelector<HTMLElement>('[data-node-id="42"]')
    const targetRow = container.querySelector<HTMLElement>('[data-node-id="77"]')
    Object.defineProperty(document, 'elementFromPoint', {
      configurable: true,
      value: () => targetRow,
    })

    // User touches row 42 and immediately swipes vertically to scroll (before 450ms)
    act(() => {
      sourceRow?.dispatchEvent(
        Object.assign(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 50, clientY: 50 }), {
          pointerType: 'touch',
          pointerId: 1,
        }),
      )
      vi.advanceTimersByTime(100)
      window.dispatchEvent(
        Object.assign(new MouseEvent('pointermove', { bubbles: true, clientX: 50, clientY: 90 }), {
          pointerType: 'touch',
          pointerId: 1,
        }),
      )
      vi.advanceTimersByTime(500)
      window.dispatchEvent(
        Object.assign(new MouseEvent('pointerup', { bubbles: true, clientX: 50, clientY: 90 }), {
          pointerType: 'touch',
          pointerId: 1,
        }),
      )
    })

    expect(container.querySelector('[data-root-drop="true"]')).toBeNull()
    expect(onMoveDeck).not.toHaveBeenCalled()

    if (elementFromPointDescriptor) {
      Object.defineProperty(document, 'elementFromPoint', elementFromPointDescriptor)
    } else {
      delete (document as Partial<Document>).elementFromPoint
    }
    vi.useRealTimers()
  })

  it('activates touch drag only after holding for 450ms and commits move on pointerup, but cancels on pointercancel', () => {
    vi.useFakeTimers()
    const onMoveDeck = vi.fn().mockResolvedValue(undefined)
    const targetDeck: DeckNode = {
      ...deck,
      id: 77,
      name: 'N2 Vocabulary',
    }
    const elementFromPointDescriptor = Object.getOwnPropertyDescriptor(document, 'elementFromPoint')

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck, targetDeck]}
            adminMode={false}
            onAction={vi.fn()}
            onMoveDeck={onMoveDeck}
          />
        </MemoryRouter>,
      )
    })

    const sourceRow = container.querySelector<HTMLElement>('[data-node-id="42"]')
    const targetRow = container.querySelector<HTMLElement>('[data-node-id="77"]')
    Object.defineProperty(document, 'elementFromPoint', {
      configurable: true,
      value: () => targetRow,
    })

    // 1. Long-press then pointercancel should NOT call onMoveDeck
    act(() => {
      sourceRow?.dispatchEvent(
        Object.assign(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 50, clientY: 50 }), {
          pointerType: 'touch',
          pointerId: 1,
        }),
      )
      vi.advanceTimersByTime(460)
    })
    expect(container.querySelector('[data-root-drop="true"]')).not.toBeNull()

    act(() => {
      window.dispatchEvent(
        Object.assign(new MouseEvent('pointermove', { bubbles: true, clientX: 50, clientY: 120 }), {
          pointerType: 'touch',
          pointerId: 1,
        }),
      )
    })
    act(() => {
      window.dispatchEvent(new Event('pointercancel'))
    })
    expect(onMoveDeck).not.toHaveBeenCalled()
    expect(container.querySelector('[data-root-drop="true"]')).toBeNull()

    // 2. Long-press then move to targetRow and pointerup SHOULD call onMoveDeck
    act(() => {
      sourceRow?.dispatchEvent(
        Object.assign(new MouseEvent('pointerdown', { bubbles: true, button: 0, clientX: 50, clientY: 50 }), {
          pointerType: 'touch',
          pointerId: 2,
        }),
      )
      vi.advanceTimersByTime(460)
    })
    act(() => {
      window.dispatchEvent(
        Object.assign(new MouseEvent('pointermove', { bubbles: true, clientX: 50, clientY: 120 }), {
          pointerType: 'touch',
          pointerId: 2,
        }),
      )
    })
    act(() => {
      window.dispatchEvent(
        Object.assign(new MouseEvent('pointerup', { bubbles: true, clientX: 50, clientY: 120 }), {
          pointerType: 'touch',
          pointerId: 2,
        }),
      )
    })

    expect(onMoveDeck).toHaveBeenCalledWith(42, 77)

    if (elementFromPointDescriptor) {
      Object.defineProperty(document, 'elementFromPoint', elementFromPointDescriptor)
    } else {
      delete (document as Partial<Document>).elementFromPoint
    }
    vi.useRealTimers()
  })

  it('activates study on the second touch tap when the deck is already selected', () => {
    const onSelect = vi.fn()
    const onActivate = vi.fn()

    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            selectedDeckId={null}
            onSelect={onSelect}
            onActivate={onActivate}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const row = container.querySelector<HTMLElement>('[data-node-id="42"]')

    // First tap on unselected deck selects it without activating study
    act(() => {
      row?.dispatchEvent(
        Object.assign(new MouseEvent('pointerdown', { bubbles: true, button: 0 }), {
          pointerType: 'touch',
        }),
      )
      row?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(onSelect).toHaveBeenCalledTimes(1)
    expect(onActivate).not.toHaveBeenCalled()

    // Re-render with deck 42 selected, then tap again on touch -> activates study
    act(() => {
      root.render(
        <MemoryRouter>
          <DeckTree
            nodes={[deck]}
            adminMode={false}
            selectedDeckId={42}
            onSelect={onSelect}
            onActivate={onActivate}
            onAction={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    const selectedRow = container.querySelector<HTMLElement>('[data-node-id="42"]')
    act(() => {
      selectedRow?.dispatchEvent(
        Object.assign(new MouseEvent('pointerdown', { bubbles: true, button: 0 }), {
          pointerType: 'touch',
        }),
      )
      selectedRow?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    expect(onActivate).toHaveBeenCalledWith(deck)
  })
})

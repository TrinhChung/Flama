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
})

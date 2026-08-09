// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
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
        <DeckTree
          nodes={[deck]}
          adminMode={false}
          onSelect={onSelect}
          onActivate={onActivate}
          onAction={vi.fn()}
        />,
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
        <DeckTree
          nodes={[deck]}
          adminMode={false}
          onActivate={onActivate}
          onAction={vi.fn()}
        />,
      )
    })

    const row = container.querySelector<HTMLElement>('[data-node-id="42"]')
    act(() => {
      row?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    })

    expect(onActivate).toHaveBeenCalledWith(deck)
  })
})

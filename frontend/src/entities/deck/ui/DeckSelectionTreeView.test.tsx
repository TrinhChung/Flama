// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DeckSelectionTreeView, type DeckOption } from './DeckSelectionTreeView'

const rootDeck: DeckOption = {
  id: 520,
  parent_id: null,
  name: '徹底N1',
  path: '徹底N1',
}

const childDecks: DeckOption[] = Array.from({ length: 170 }, (_, index) => ({
  id: 521 + index,
  parent_id: rootDeck.id,
  name: `Bài ${String(index + 1).padStart(3, '0')}`,
  path: `${rootDeck.path}::Bài ${String(index + 1).padStart(3, '0')}`,
}))

describe('DeckSelectionTreeView', () => {
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

  it('keeps large root folders collapsed until the user expands them', () => {
    act(() => {
      root.render(
        <DeckSelectionTreeView
          deckOptions={[rootDeck, ...childDecks]}
          selectedDeckId={String(rootDeck.id)}
          onSelectDeck={vi.fn()}
        />,
      )
    })

    expect(container.textContent).not.toContain('Bài 170')

    const expandButton = container.querySelector<HTMLButtonElement>(
      '[aria-label="Mở rộng deck 徹底N1"]',
    )
    act(() => expandButton?.click())
    expect(container.textContent).toContain('Bài 170')

    const collapseAllButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Thu gọn tất cả'),
    )
    act(() => collapseAllButton?.click())
    expect(container.textContent).not.toContain('Bài 170')
  })

  it('opens only the ancestor branch needed to reveal a preselected child deck', () => {
    act(() => {
      root.render(
        <DeckSelectionTreeView
          deckOptions={[rootDeck, ...childDecks]}
          selectedDeckId={String(childDecks[169].id)}
          onSelectDeck={vi.fn()}
        />,
      )
    })

    expect(container.textContent).toContain('Bài 170')
  })
})

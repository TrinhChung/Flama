// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { PublishDeckOption } from '../publishApi'
import { PublishDeckTree } from './PublishDeckTree'

const decks: PublishDeckOption[] = [
  {
    id: 1,
    name: 'Bộ cha đã chia sẻ',
    parent_id: null,
    card_count: 170,
    is_selectable: false,
    block_code: 'already_shared',
    block_reason: 'Bộ thẻ này đã được chia sẻ và không thể chia sẻ lại.',
    shared_item_id: 'shared-root',
  },
  {
    id: 2,
    name: 'Bộ con',
    parent_id: 1,
    card_count: 20,
    is_selectable: false,
    block_code: 'ancestor_shared',
    block_reason: "Không thể chia sẻ bộ con vì bộ cha 'Bộ cha đã chia sẻ' đã được chia sẻ.",
    shared_item_id: 'shared-root',
  },
  {
    id: 3,
    name: 'Clone từ Marketplace',
    parent_id: null,
    card_count: 50,
    is_selectable: false,
    block_code: 'marketplace_clone',
    block_reason: 'Bộ thẻ được cài từ Marketplace không thể chia sẻ lại.',
    shared_item_id: null,
  },
  {
    id: 4,
    name: 'Đồng bộ từ Anki',
    parent_id: null,
    card_count: 75,
    is_selectable: true,
    block_code: null,
    block_reason: null,
    shared_item_id: null,
  },
]

describe('PublishDeckTree', () => {
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

  it('keeps hierarchy and prevents selecting shared or cloned decks', () => {
    const onSelect = vi.fn()
    act(() => {
      root.render(<PublishDeckTree decks={decks} selectedDeckId="" onSelectDeck={onSelect} />)
    })

    const expandParent = container.querySelector<HTMLButtonElement>(
      '[aria-label="Mở rộng bộ Bộ cha đã chia sẻ"]',
    )
    act(() => expandParent?.click())

    const blockedRows = container.querySelectorAll<HTMLElement>('[aria-disabled="true"]')
    expect(blockedRows).toHaveLength(3)
    act(() => blockedRows[0]?.click())
    act(() => blockedRows[1]?.click())
    act(() => blockedRows[2]?.click())
    expect(onSelect).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Bộ con')
    expect(container.textContent).toContain('Từ Marketplace')
  })

  it('allows selecting a self-created or Anki-synced deck', () => {
    const onSelect = vi.fn()
    act(() => {
      root.render(<PublishDeckTree decks={decks} selectedDeckId="" onSelectDeck={onSelect} />)
    })

    const ankiRow = Array.from(container.querySelectorAll<HTMLElement>('[role="treeitem"]')).find(
      (row) => row.textContent?.includes('Đồng bộ từ Anki'),
    )
    act(() => ankiRow?.click())
    expect(onSelect).toHaveBeenCalledWith(decks[3])
  })
})

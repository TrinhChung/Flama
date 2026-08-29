// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PublishNoteTypeSelector,
  type PublishNoteTypeOption,
} from './PublishNoteTypeSelector'

const mockNoteTypes: PublishNoteTypeOption[] = [
  {
    id: 'nt-published-1',
    name: 'Mẫu thẻ đã đăng',
    publish_status: 'published',
    field_count: 5,
    templates: [{ name: 'Front' }, { name: 'Back' }],
  },
  {
    id: 'nt-unlisted-2',
    name: 'Mẫu thẻ unlisted',
    publish_status: 'unlisted',
    field_count: 3,
  },
  {
    id: 'nt-marketplace-3',
    name: 'Mẫu thẻ từ Marketplace',
    is_marketplace_install: true,
    field_count: 4,
  },
  {
    id: 'nt-available-4',
    name: 'Mẫu thẻ cá nhân chưa xuất bản',
    publish_status: 'private',
    field_count: 6,
    templates: [{ name: 'Card 1' }],
  },
]

describe('PublishNoteTypeSelector', () => {
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

  it('disables already published and marketplace installed note types with cursor-not-allowed and prevents selection', () => {
    const onSelect = vi.fn()
    act(() => {
      root.render(
        <PublishNoteTypeSelector
          noteTypes={mockNoteTypes}
          selectedNoteTypeId=""
          onSelectNoteType={onSelect}
        />
      )
    })

    const blockedItems = container.querySelectorAll<HTMLElement>('[aria-disabled="true"]')
    expect(blockedItems).toHaveLength(3)

    // Check styling on blocked items
    blockedItems.forEach((item) => {
      expect(item.className).toContain('cursor-not-allowed')
      expect(item.className).toContain('bg-muted/20')
      expect(item.className).toContain('opacity-60')
    })

    // Click on published item
    act(() => {
      blockedItems[0].click()
    })
    // Click on unlisted item
    act(() => {
      blockedItems[1].click()
    })
    // Click on marketplace install item
    act(() => {
      blockedItems[2].click()
    })

    expect(onSelect).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Đã xuất bản')
    expect(container.textContent).toContain('Từ Marketplace')
  })

  it('allows selecting an unpublished personal note type', () => {
    const onSelect = vi.fn()
    act(() => {
      root.render(
        <PublishNoteTypeSelector
          noteTypes={mockNoteTypes}
          selectedNoteTypeId=""
          onSelectNoteType={onSelect}
        />
      )
    })

    const availableItem = Array.from(
      container.querySelectorAll<HTMLElement>('[role="option"]')
    ).find((item) => item.textContent?.includes('Mẫu thẻ cá nhân chưa xuất bản'))

    expect(availableItem).toBeDefined()
    expect(availableItem?.getAttribute('aria-disabled')).toBe('false')
    expect(availableItem?.className).toContain('cursor-pointer')

    act(() => {
      availableItem?.click()
    })

    expect(onSelect).toHaveBeenCalledWith(mockNoteTypes[3])
  })

  it('highlights the currently selected note type', () => {
    act(() => {
      root.render(
        <PublishNoteTypeSelector
          noteTypes={mockNoteTypes}
          selectedNoteTypeId="nt-available-4"
          onSelectNoteType={vi.fn()}
        />
      )
    })

    const selectedItem = container.querySelector<HTMLElement>('[aria-selected="true"]')
    expect(selectedItem).toBeDefined()
    expect(selectedItem?.textContent).toContain('Mẫu thẻ cá nhân chưa xuất bản')
    expect(selectedItem?.className).toContain('border-primary/40')
    expect(selectedItem?.className).toContain('bg-primary/10')
  })
})

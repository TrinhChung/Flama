// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DiffItem, DiffSummary } from '../types'
import { DiffWorkspace } from './DiffWorkspace'

const summary: DiffSummary = {
  total: 1,
  entities: 1,
  added: 0,
  modified: 1,
  removed: 0,
  conflicts: 0,
}

const items: DiffItem[] = [
  {
    id: 'change-1',
    change_type: 'modified',
    entity_kind: 'note_field',
    entity_id: 'note-1',
    note_label: '食べる',
    field_name: 'Meaning',
    before_value: 'old meaning',
    after_value: 'new meaning',
  },
]

describe('DiffWorkspace', () => {
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

  it('keeps field values lazy until the compact row is expanded', () => {
    act(() => {
      root.render(
        <DiffWorkspace
          summary={summary}
          items={items}
          filters={{ query: '', changeType: 'all' }}
          onFiltersChange={vi.fn()}
        />,
      )
    })

    expect(container.textContent).not.toContain('old meaning')
    expect(container.textContent).not.toContain('new meaning')

    const row = container.querySelector<HTMLButtonElement>('[aria-expanded="false"]')
    act(() => row?.click())

    expect(container.textContent).toContain('old meaning')
    expect(container.textContent).toContain('new meaning')
  })

  it('delegates change filters so the page can reset its server cursor', () => {
    const onFiltersChange = vi.fn()
    act(() => {
      root.render(
        <DiffWorkspace
          summary={{ ...summary, added: 4, total: 5 }}
          items={items}
          filters={{ query: '', changeType: 'all' }}
          onFiltersChange={onFiltersChange}
        />,
      )
    })

    const addedFilter = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Thêm4'),
    )
    act(() => addedFilter?.click())

    expect(onFiltersChange).toHaveBeenCalledWith({ query: '', changeType: 'added' })
  })
})

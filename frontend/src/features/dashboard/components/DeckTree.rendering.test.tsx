// @vitest-environment jsdom

import { act, useCallback, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { DeckNode } from '../types'
import { ESTIMATED_ROW_HEIGHT, OVERSCAN_ROWS } from '../hooks/useWindowedRows'
import { DeckTree } from './DeckTree'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

// DeckTree and every DeckRow call useTranslation once per render, so counting
// calls tells how many components rendered.
const renders = vi.hoisted(() => ({ count: 0 }))
vi.mock('react-i18next', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-i18next')>()
  return {
    ...actual,
    useTranslation: (...args: Parameters<typeof actual.useTranslation>) => {
      renders.count += 1
      return actual.useTranslation(...args)
    },
  }
})

function deck(id: number, children: DeckNode[] = [], parentId: number | null = null): DeckNode {
  return {
    id,
    parent_id: parentId,
    name: `Deck ${id}`,
    depth: parentId === null ? 0 : 1,
    study_url: `/study?deck_id=${id}`,
    counts: { new: 0, learning: 0, due: 0 },
    move: { alias: `deck-${id}`, token: '', parent_alias: null, parent_token: null },
    actions: { rename: '', move: '', delete: '', reset: '', share: '' },
    children,
  }
}

const onAction = vi.fn()
const onMoveDeck = vi.fn().mockResolvedValue(undefined)

// Mirrors DashboardPage: row callbacks are stable across renders.
function SelectableTree({ nodes }: { nodes: DeckNode[] }) {
  const [selected, setSelected] = useState<number | null>(null)
  const onSelect = useCallback((node: DeckNode) => setSelected(node.id), [])
  return (
    <MemoryRouter>
      <DeckTree
        nodes={nodes}
        adminMode={false}
        selectedDeckId={selected}
        onSelect={onSelect}
        onAction={onAction}
        onMoveDeck={onMoveDeck}
      />
    </MemoryRouter>
  )
}

const pointer = (type: string, x: number, y: number) =>
  Object.assign(new MouseEvent(type, { bubbles: true, button: 0, clientX: x, clientY: y }), {
    pointerType: 'mouse',
    pointerId: 3,
  })

describe('DeckTree render scope and windowing', () => {
  let container: HTMLDivElement
  let root: Root
  let elementFromPointDescriptor: PropertyDescriptor | undefined

  beforeEach(() => {
    localStorage.clear()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    elementFromPointDescriptor = Object.getOwnPropertyDescriptor(document, 'elementFromPoint')
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
    localStorage.clear()
    if (elementFromPointDescriptor) {
      Object.defineProperty(document, 'elementFromPoint', elementFromPointDescriptor)
    } else {
      delete (document as Partial<Document>).elementFromPoint
    }
    vi.restoreAllMocks()
  })

  const row = (id: number) => container.querySelector<HTMLElement>(`[data-node-id="${id}"]`)
  const renderedIds = () =>
    Array.from(container.querySelectorAll<HTMLElement>('[data-node-id]')).map((el) => Number(el.dataset.nodeId))

  it('re-renders only the rows whose selection or drop target changes', () => {
    const nodes = [1, 2, 3, 4, 5, 6].map((id) => deck(id))
    let hit: Element | null = null
    Object.defineProperty(document, 'elementFromPoint', { configurable: true, value: () => hit })
    act(() => root.render(<SelectableTree nodes={nodes} />))

    renders.count = 0
    act(() => row(2)?.click())
    expect(renders.count).toBe(2) // tree + newly selected row

    act(() => row(1)?.dispatchEvent(pointer('pointerdown', 5, 5)))
    hit = row(3)
    act(() => window.dispatchEvent(pointer('pointermove', 5, 40)))
    renders.count = 0
    hit = row(4)
    act(() => window.dispatchEvent(pointer('pointermove', 5, 80)))
    expect(renders.count).toBe(3) // tree + row leaving hover + row entering hover

    act(() => window.dispatchEvent(new Event('pointercancel')))
  })

  it('renders only the toggled row plus its revealed children when expanding', () => {
    const nodes = [deck(1, [deck(11, [], 1), deck(12, [], 1)]), deck(2), deck(3)]
    act(() => root.render(<SelectableTree nodes={nodes} />))

    renders.count = 0
    act(() => row(1)?.querySelector<HTMLButtonElement>('.tree-toggle')?.click())
    expect(renderedIds()).toEqual([1, 11, 12, 2, 3])
    expect(renders.count).toBe(4) // tree + toggled row + two mounted children
  })

  it('renders every row without spacers for ordinary trees', () => {
    const nodes = Array.from({ length: 20 }, (_, index) => deck(index + 1))
    act(() => root.render(<SelectableTree nodes={nodes} />))

    expect(renderedIds()).toHaveLength(20)
    expect(container.querySelector('[data-virtual-spacer]')).toBeNull()
  })

  it('mounts only rows near the viewport for very long trees and follows window scroll', async () => {
    const nodes = Array.from({ length: 400 }, (_, index) => deck(index + 1))
    act(() => root.render(<SelectableTree nodes={nodes} />))

    const viewportRows = Math.ceil(window.innerHeight / ESTIMATED_ROW_HEIGHT)
    const firstEnd = viewportRows + OVERSCAN_ROWS
    expect(renderedIds()).toEqual(Array.from({ length: firstEnd }, (_, index) => index + 1))
    expect(container.querySelector<HTMLElement>('[data-virtual-spacer="after"]')?.style.height)
      .toBe(`${(400 - firstEnd) * ESTIMATED_ROW_HEIGHT}px`)

    const anchor = container.querySelector<HTMLElement>('[data-virtual-spacer="before"]')!
    const scrolledRows = 200
    vi.spyOn(anchor, 'getBoundingClientRect').mockReturnValue({
      top: -scrolledRows * ESTIMATED_ROW_HEIGHT,
    } as DOMRect)
    await act(async () => {
      window.dispatchEvent(new Event('scroll'))
      await new Promise((resolve) => setTimeout(resolve, 40))
    })

    const start = scrolledRows - OVERSCAN_ROWS
    const ids = renderedIds()
    expect(ids[0]).toBe(start + 1)
    expect(ids.length).toBe(viewportRows + 2 * OVERSCAN_ROWS)
    expect(anchor.style.height).toBe(`${start * ESTIMATED_ROW_HEIGHT}px`)
    expect(row(1)).toBeNull()
  })

  async function scrollTo(rowsAbove: number) {
    const anchor = container.querySelector<HTMLElement>('[data-virtual-spacer="before"]')!
    vi.spyOn(anchor, 'getBoundingClientRect').mockReturnValue({
      top: -rowsAbove * ESTIMATED_ROW_HEIGHT,
    } as DOMRect)
    await act(async () => {
      window.dispatchEvent(new Event('scroll'))
      await new Promise((resolve) => setTimeout(resolve, 40))
    })
  }

  it('keeps focus in the list while the focused row is scrolled out, then returns it', async () => {
    const nodes = Array.from({ length: 400 }, (_, index) => deck(index + 1))
    act(() => root.render(<SelectableTree nodes={nodes} />))
    const list = container.querySelector<HTMLElement>('.deck-list')!

    act(() => row(5)?.focus())
    expect(document.activeElement).toBe(row(5))

    await scrollTo(200)
    expect(row(5)).toBeNull()
    expect(document.activeElement).toBe(list)

    await scrollTo(0)
    expect(document.activeElement).toBe(row(5))
  })

  it('does not pull focus back after the learner moved focus elsewhere', async () => {
    const nodes = Array.from({ length: 400 }, (_, index) => deck(index + 1))
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    act(() => root.render(<SelectableTree nodes={nodes} />))

    act(() => row(5)?.focus())
    await scrollTo(200)
    act(() => outside.focus())
    await scrollTo(0)

    expect(document.activeElement).toBe(outside)
    outside.remove()
  })

  it('mounts every row once browser find is opened so Ctrl+F can match any deck', () => {
    const nodes = Array.from({ length: 400 }, (_, index) => deck(index + 1))
    act(() => root.render(<SelectableTree nodes={nodes} />))
    expect(renderedIds().length).toBeLessThan(400)

    act(() => {
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'f', ctrlKey: true }))
    })

    expect(renderedIds()).toHaveLength(400)
    expect(container.querySelector('[data-virtual-spacer]')).toBeNull()
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import i18n, { i18nReady } from '@/shared/config/i18n'
import { groupContributionChanges } from '../../model/noteChanges'
import type { ChangeRequestItem, NoteContext } from '../../types'
import { NoteChangeList } from './NoteChangeList'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function item(id: string, noteId: string, label: string, before: string, after: string): ChangeRequestItem {
  return { id, change_type: 'note_field_set', source_ref_id: noteId, path_key: 'Meaning',
    before_value: before, after_value: after, effective_after_value: after, is_conflict: false,
    metadata: { field_name: 'Meaning', source_note_id: noteId, source_note_label: label } }
}

const root5 = { key: '5', path: ['N5'], order: 0 }
const lesson = { key: '7', path: ['N5', 'Bài 1'], order: 1 }

describe('changed notes list', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(async () => {
    await i18nReady
    await i18n.changeLanguage('vi')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
  })

  async function render(contexts: Record<string, NoteContext>) {
    const grouped = groupContributionChanges([
      item('a', 'n1', '犬', 'dog', 'hound'),
      item('b', 'n2', '猫', 'cat', 'kitty'),
      item('c', 'n3', '牛', 'cow', 'ox'),
    ])
    await act(async () => root.render(
      <NoteChangeList
        grouped={grouped}
        fieldDefs={[{ name: 'Meaning', field_type: 'text' }]}
        noteContexts={contexts}
        totalNotes={3}
        query=""
        onQueryChange={() => {}}
      />,
    ))
  }

  function visibleText() {
    const clone = container.cloneNode(true) as HTMLElement
    clone.querySelectorAll('.sr-only').forEach((element) => element.remove())
    return clone.textContent || ''
  }

  it('names the two sides once for the whole list, not on every field', async () => {
    await render({})
    expect(visibleText().match(/Bản hiện tại/g)).toHaveLength(1)
    expect(visibleText().match(/Bản đề xuất/g)).toHaveLength(1)
    expect(visibleText()).not.toContain('Đã sửa')
    expect(container.querySelectorAll('.sr-only').length).toBeGreaterThanOrEqual(6)
  })

  it('groups notes under their sub-decks and folds a sub-deck on request', async () => {
    await render({
      n1: { label: '犬', values: null, deck: lesson },
      n2: { label: '猫', values: null, deck: root5 },
      n3: { label: '牛', values: null, deck: lesson },
    })
    const headings = Array.from(container.querySelectorAll('button[aria-expanded]'))
      .filter((button) => button.querySelector('svg.lucide-folder'))
    expect(headings.map((heading) => heading.textContent)).toEqual(['N51 note', 'Bài 12 note'])
    const cards = () => Array.from(container.querySelectorAll('article')).map((card) => card.getAttribute('aria-label'))
    expect(cards()).toEqual(['猫', '犬', '牛'])
    await act(async () => (headings[1] as HTMLButtonElement).click())
    expect(cards()).toEqual(['猫'])
  })

  it('leaves out folder headings when every note sits in the deck itself', async () => {
    await render({
      n1: { label: '犬', values: null, deck: root5 },
      n2: { label: '猫', values: null, deck: root5 },
      n3: { label: '牛', values: null, deck: root5 },
    })
    expect(container.querySelector('svg.lucide-folder')).toBeNull()
  })
})

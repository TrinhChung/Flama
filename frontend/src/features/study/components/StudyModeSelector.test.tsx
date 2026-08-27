// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyModeSelector } from './StudyModeSelector'
import type { AppliedComposition } from '../types'

const mockCompositions: AppliedComposition[] = [
  {
    composition_id: 'comp:notetype:nt-1:template:tpl-1',
    mode_key: 'flashcard',
    note_type_id: 'nt-1',
    template_id: 'tpl-1',
    template_name: 'Front -> Back',
    is_default: true,
    interaction_key: 'review.four-rating',
    trigger_key: 'scheduler.review',
    trigger_contract_version: '1',
    algorithm_key: 'legacy-anki',
    algorithm_version: '1.0.0',
  },
  {
    composition_id: 'comp:notetype:nt-1:template:tpl-2',
    mode_key: 'flashcard',
    note_type_id: 'nt-1',
    template_id: 'tpl-2',
    template_name: 'Back -> Front',
    is_default: false,
    interaction_key: 'review.four-rating',
    trigger_key: 'scheduler.review',
    trigger_contract_version: '1',
    algorithm_key: 'legacy-anki',
    algorithm_version: '1.0.0',
  },
]

describe('StudyModeSelector', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders nothing when compositions length is <= 1', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StudyModeSelector
          compositions={[mockCompositions[0]]}
          onSelectComposition={vi.fn()}
        />
      )
    })

    expect(container.firstChild).toBeNull()
    await act(async () => root.unmount())
  })

  it('renders all options and handles click events', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onSelect = vi.fn()

    await act(async () => {
      root.render(
        <StudyModeSelector
          compositions={mockCompositions}
          selectedCompositionId={null}
          onSelectComposition={onSelect}
        />
      )
    })

    expect(container.textContent).toContain('Tất cả (2)')
    expect(container.textContent).toContain('Front -> Back')
    expect(container.textContent).toContain('Back -> Front')

    const buttons = container.querySelectorAll('button')
    expect(buttons.length).toBe(3)

    // Click 'Front -> Back'
    await act(async () => {
      buttons[1]?.click()
    })
    expect(onSelect).toHaveBeenCalledWith('comp:notetype:nt-1:template:tpl-1')

    // Click 'Tất cả (2)'
    await act(async () => {
      buttons[0]?.click()
    })
    expect(onSelect).toHaveBeenCalledWith(null)

    await act(async () => root.unmount())
  })
})

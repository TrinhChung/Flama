// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyModeSelector } from './StudyModeSelector'
import type { AppliedComposition, StudyCompositionGroup } from '../types'

const mockCompositions: AppliedComposition[] = [
  {
    composition_id: 'comp:notetype:nt-1:template:tpl-1',
    mode_key: 'flashcard',
    note_type_id: 'nt-1',
    note_type_name: 'Basic',
    template_id: 'tpl-1',
    template_name: 'Front -> Back',
    is_default: true,
    context_kind: 'owned',
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
    note_type_name: 'Basic',
    template_id: 'tpl-2',
    template_name: 'Back -> Front',
    is_default: false,
    context_kind: 'owned',
    interaction_key: 'review.four-rating',
    trigger_key: 'scheduler.review',
    trigger_contract_version: '1',
    algorithm_key: 'legacy-anki',
    algorithm_version: '1.0.0',
  },
]

const groups: StudyCompositionGroup[] = [{
  note_type_id: 'nt-1',
  note_type_name: 'Basic',
  compositions: mockCompositions,
}]

describe('StudyModeSelector', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders nothing when no eligible groups exist', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(<StudyModeSelector groups={[]} onSelectComposition={vi.fn()} />)
    })

    expect(container.firstChild).toBeNull()
    await act(async () => root.unmount())
  })

  it('groups exact options and never exposes an all-compositions choice', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onSelect = vi.fn()

    await act(async () => {
      root.render(
        <StudyModeSelector
          groups={groups}
          selectedCompositionId={null}
          onSelectComposition={onSelect}
        />
      )
    })

    expect(container.textContent).toContain('Basic')
    expect(container.textContent).toContain('Front -> Back')
    expect(container.textContent).toContain('Back -> Front')
    expect(container.textContent).not.toContain('Tất cả')

    const buttons = container.querySelectorAll('button')
    expect(buttons.length).toBe(2)
    await act(async () => {
      buttons[0]?.click()
    })
    expect(onSelect).toHaveBeenCalledWith('comp:notetype:nt-1:template:tpl-1')

    await act(async () => root.unmount())
  })
})

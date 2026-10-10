// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { FieldListCard } from './FieldListCard'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'

const mockFields: FieldDefItem[] = [
  { id: 'f1', name: 'Word', field_type: 'text', required: true, identity_role: 'primary', position: 0 },
  { id: 'f2', name: 'Reading', field_type: 'richtext', required: false, identity_role: null, position: 1 },
  { id: 'f3', name: 'Image', field_type: 'image', required: false, identity_role: null, position: 2 },
]

function setValue(element: HTMLInputElement, value: string) {
  const prototype = HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, 'value')!.set!.call(element, value)
  element.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('FieldListCard component', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(async () => {
    await i18n.changeLanguage('vi')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    document.body.innerHTML = ''
  })

  it('renders field list compactly without redundant type labels in rows', async () => {
    await act(async () => {
      root.render(
        <FieldListCard
          fields={mockFields}
          selectedFieldId="f1"
          isAddingField={false}
          onSelectField={vi.fn()}
          onStartAddField={vi.fn()}
          onDragStart={vi.fn()}
          onDrop={vi.fn()}
          onMoveUp={vi.fn()}
          onMoveDown={vi.fn()}
          isReordering={false}
        />
      )
    })

    // Field names must be rendered
    expect(container.textContent).toContain('Word')
    expect(container.textContent).toContain('Reading')
    expect(container.textContent).toContain('Image')

    // Verbose redundant type labels should NOT be displayed inside list rows
    // In Vietnamese, richtext is "Văn bản có định dạng", image is "Hình ảnh"
    expect(container.textContent).not.toContain('Văn bản có định dạng')
    expect(container.textContent).not.toContain('Hình ảnh')

    // Primary identity badge should be present for Word
    expect(container.textContent).toContain('id')
  })

  it('triggers onSelectField when clicking a field item', async () => {
    const onSelectField = vi.fn()
    await act(async () => {
      root.render(
        <FieldListCard
          fields={mockFields}
          selectedFieldId="f1"
          isAddingField={false}
          onSelectField={onSelectField}
          onStartAddField={vi.fn()}
          onDragStart={vi.fn()}
          onDrop={vi.fn()}
          onMoveUp={vi.fn()}
          onMoveDown={vi.fn()}
          isReordering={false}
        />
      )
    })

    const buttons = Array.from(container.querySelectorAll<HTMLButtonElement>('button[aria-pressed]'))
    expect(buttons).toHaveLength(3)

    await act(async () => {
      buttons[1].click()
    })

    expect(onSelectField).toHaveBeenCalledWith('f2')
  })

  it('supports searching/filtering fields in the list', async () => {
    await act(async () => {
      root.render(
        <FieldListCard
          fields={mockFields}
          selectedFieldId="f1"
          isAddingField={false}
          onSelectField={vi.fn()}
          onStartAddField={vi.fn()}
          onDragStart={vi.fn()}
          onDrop={vi.fn()}
          onMoveUp={vi.fn()}
          onMoveDown={vi.fn()}
          isReordering={false}
        />
      )
    })

    const searchInput = container.querySelector('input[aria-label="Tìm trường…"]') as HTMLInputElement
    expect(searchInput).not.toBeNull()

    await act(async () => {
      setValue(searchInput, 'Read')
    })

    expect(container.textContent).toContain('Reading')
    expect(container.textContent).not.toContain('Image')
  })
})

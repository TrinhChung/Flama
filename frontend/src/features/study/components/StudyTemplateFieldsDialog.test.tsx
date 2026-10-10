// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StudyTemplateFieldsDialog, type StudyTemplateFieldsDialogProps } from './StudyTemplateFieldsDialog'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement

beforeEach(() => {
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(async () => {
  await act(async () => root.unmount())
  document.body.replaceChildren()
})

function props(overrides: Partial<StudyTemplateFieldsDialogProps> = {}): StudyTemplateFieldsDialogProps {
  return {
    open: true,
    onOpenChange: vi.fn(),
    templateName: 'Basic',
    entry: {
      input_schema: [
        { key: 'front', label: 'Front', type: 'text', required: true },
        { key: 'audio', label: 'Audio', type: 'audio', required: false },
      ],
      field_defs: [
        { id: 'f1', name: 'Word', field_type: 'text' },
        { id: 'f2', name: 'Reading', field_type: 'text' },
        { id: 'f3', name: 'Audio Clip', field_type: 'audio' },
      ],
      input_bindings: { front: 'f1', audio: 'f3' },
      warnings: [],
    },
    mapping: { inputBindings: { front: 'f1', audio: 'f3' }, staleInputs: [], customized: false },
    onSave: vi.fn(),
    ...overrides,
  }
}

async function render(dialogProps: StudyTemplateFieldsDialogProps) {
  await act(async () => root.render(<StudyTemplateFieldsDialog {...dialogProps} />))
}

function button(label: string) {
  const result = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="dialog"] button'))
    .find(element => element.textContent === label)
  expect(result).toBeDefined()
  return result!
}

describe('StudyTemplateFieldsDialog', () => {
  it('saves an explicitly empty input without falling back to its default', async () => {
    const dialogProps = props()
    await render(dialogProps)
    const selects = document.querySelectorAll<HTMLSelectElement>('[role="dialog"] select')
    expect(Array.from(selects[1].options).map(option => option.value)).toEqual(['', 'f3'])
    await act(async () => {
      selects[1].value = ''
      selects[1].dispatchEvent(new Event('change', { bubbles: true }))
    })
    expect(dialogProps.onSave).not.toHaveBeenCalled()
    await act(async () => button('Lưu').click())
    expect(dialogProps.onSave).toHaveBeenCalledWith({ front: 'f1', audio: null })
  })

  it('cancels a draft without saving and restores persisted bindings when reopened', async () => {
    const dialogProps = props()
    await render(dialogProps)
    await act(async () => {
      const select = document.querySelector<HTMLSelectElement>('[role="dialog"] select')!
      select.value = 'f2'
      select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    await act(async () => button('Hủy').click())
    expect(dialogProps.onOpenChange).toHaveBeenCalledWith(false)
    expect(dialogProps.onSave).not.toHaveBeenCalled()
    await render({ ...dialogProps, open: false })
    await render(dialogProps)
    expect(document.querySelector<HTMLSelectElement>('[role="dialog"] select')!.value).toBe('f1')
  })

  it('resets a customized map with null instead of persisting empty inputs', async () => {
    const dialogProps = props({ mapping: { inputBindings: { front: 'f2', audio: null }, staleInputs: [], customized: true } })
    await render(dialogProps)
    await act(async () => button('Về mặc định').click())
    expect(dialogProps.onSave).toHaveBeenCalledWith(null)
  })

  it('blocks edits and dismissal while a map is being saved for the active session', async () => {
    const dialogProps = props({ saving: true, appliesToSession: true })
    await render(dialogProps)
    expect(button('Lưu & áp dụng').disabled).toBe(true)
    expect(button('Hủy').disabled).toBe(true)
    expect(Array.from(document.querySelectorAll<HTMLSelectElement>('[role="dialog"] select')).every(select => select.disabled)).toBe(true)
    await act(async () => {
      document.querySelector<HTMLButtonElement>('[role="dialog"] [data-slot="dialog-close"]')!.click()
    })
    expect(dialogProps.onOpenChange).not.toHaveBeenCalled()
    expect(dialogProps.onSave).not.toHaveBeenCalled()
  })

  it('does not offer to save a template without inputs', async () => {
    const dialogProps = props({ entry: { input_schema: [], field_defs: [], input_bindings: {}, warnings: [] } })
    await render(dialogProps)
    expect(document.body.textContent).toContain('Template này không có input cần thiết lập.')
    expect(button('Lưu').disabled).toBe(true)
    expect(dialogProps.onSave).not.toHaveBeenCalled()
  })
})

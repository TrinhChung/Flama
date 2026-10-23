// @vitest-environment jsdom

import { act, useState } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { prefersMultilineEditor } from '../lib/noteFieldLayout'
import { NoteFieldEditor, type NoteFieldEditorProps } from './NoteFieldEditor'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function ControlledField({ initial, ...props }: Omit<NoteFieldEditorProps, 'value' | 'onChange' | 'initialValue'> & { initial: string }) {
  const [value, setValue] = useState<unknown>(initial)
  return <NoteFieldEditor {...props} value={value} initialValue={initial} onChange={(_, next) => setValue(next)} />
}

describe('NoteFieldEditor', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  function type(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
    const proto = element instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLTextAreaElement.prototype
    Object.getOwnPropertyDescriptor(proto, 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  }

  it('keeps the same focused input while typing past 50 characters', async () => {
    await act(async () => root.render(<ControlledField field={{ name: 'Word' }} initial="" />))
    const input = container.querySelector('input')!
    input.focus()
    let text = ''
    for (let index = 0; index < 70; index++) {
      text += 'a'
      await act(async () => type(input, text))
      expect(document.activeElement).toBe(input)
    }
    expect(container.querySelector('textarea')).toBeNull()
    expect(input.value).toHaveLength(70)
  })

  it('keeps a textarea when a long value is shortened', async () => {
    await act(async () => root.render(<ControlledField field={{ name: 'Word' }} initial={'x'.repeat(80)} />))
    const textarea = container.querySelector('textarea')!
    await act(async () => type(textarea, 'x'))
    expect(container.querySelector('textarea')).toBe(textarea)
    expect(container.querySelector('input')).toBeNull()
  })

  it('picks multiline from field type, field name and the stored value only', () => {
    expect(prefersMultilineEditor({ name: 'Back', field_type: 'markdown' }, '')).toBe(true)
    expect(prefersMultilineEditor({ name: 'Back', field_type: 'richtext' }, '')).toBe(true)
    expect(prefersMultilineEditor({ name: 'Meaning' }, '')).toBe(true)
    expect(prefersMultilineEditor({ name: 'Example sentence' }, '')).toBe(true)
    expect(prefersMultilineEditor({ name: 'Word' }, 'a\nb')).toBe(true)
    expect(prefersMultilineEditor({ name: 'Word' }, 'x'.repeat(51))).toBe(true)
    expect(prefersMultilineEditor({ name: 'Word' }, 'x'.repeat(50))).toBe(false)
    expect(prefersMultilineEditor({ name: 'Word', field_type: 'text' }, undefined)).toBe(false)
  })

  it('renders media and array fields with their dedicated editors', async () => {
    await act(async () => root.render(
      <>
        <NoteFieldEditor field={{ name: 'Picture', field_type: 'image' }} value="" onChange={() => {}} />
        <NoteFieldEditor field={{ name: 'Answer', field_type: 'array' }} value={['a', 'b']} onChange={() => {}} />
      </>,
    ))
    expect(container.querySelector('[aria-label="Xem trước Picture"]')).not.toBeNull()
    expect(container.querySelector<HTMLTextAreaElement>('[aria-label="Answer"]')!.value).toBe('a\nb')
  })

  it('keeps each caller density: compact for Browse, touch with a multiline hint for Study', async () => {
    await act(async () => root.render(
      <>
        <NoteFieldEditor field={{ name: 'Word', required: true }} value="" onChange={() => {}} />
        <NoteFieldEditor field={{ name: 'Meaning' }} value="" onChange={() => {}} density="touch" multilineHint="nhiều dòng" placeholder="Nhập Meaning…" />
      </>,
    ))
    const input = container.querySelector('input')!
    expect(input.className).toContain('h-9 text-xs sm:text-sm rounded-lg bg-muted/50')
    expect(input.className).not.toContain('focus:bg-background')
    expect(container.querySelector('label')!.textContent).toBe('Word *')

    const textarea = container.querySelector('textarea')!
    expect(textarea.placeholder).toBe('Nhập Meaning…')
    expect(textarea.className).toContain('text-base sm:text-sm rounded-xl leading-relaxed resize-y bg-muted/50 focus:bg-background transition-colors')
    expect(container.querySelectorAll('label')[1].textContent).toContain('nhiều dòng')
  })
})

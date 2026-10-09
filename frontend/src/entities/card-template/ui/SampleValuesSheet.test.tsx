// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SampleValuesSheet } from './SampleValuesSheet'
import { inputSchemaPreviewFields } from '../lib/previewFields'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function type(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value')!.set!.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
}

describe('SampleValuesSheet', () => {
  let container: HTMLDivElement
  let root: Root
  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    document.body.replaceChildren()
  })

  const items = [
    { key: 'Word', label: 'Từ vựng', type: 'text' },
    { key: 'Meaning', label: 'Nghĩa', type: 'markdown', placeholder: 'Nghĩa mặc định' },
    { key: 'Audio', label: 'Phát âm', type: 'audio' },
  ]

  it('uses an input per text item, a textarea for formatted text and a hint for media', async () => {
    const onChange = vi.fn()
    await act(async () => root.render(<SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="sample"
      items={items} values={{ Word: 'neko' }} onChange={onChange} onReset={vi.fn()} />))
    const word = document.querySelector<HTMLInputElement>('#sample-Word')!
    expect(word.tagName).toBe('INPUT')
    expect(word.value).toBe('neko')
    const meaning = document.querySelector<HTMLTextAreaElement>('#sample-Meaning')!
    expect(meaning.tagName).toBe('TEXTAREA')
    expect(meaning.placeholder).toBe('Nghĩa mặc định')
    expect(document.querySelector('#sample-Audio')).toBeNull()
    expect(document.body.textContent).toContain('Preview dùng mẫu media hệ thống an toàn.')
    // Only explicit samples are marked as overrides.
    expect(document.body.textContent?.match(/Mẫu tùy chỉnh/g)).toHaveLength(1)

    await type(meaning, 'con mèo')
    expect(onChange).toHaveBeenLastCalledWith('Meaning', 'con mèo')
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Xem trước giá trị rỗng')!.click())
    expect(onChange).toHaveBeenLastCalledWith('Audio', '')
  })

  it('keeps prototype-named keys empty and resets through the callback', async () => {
    const onReset = vi.fn()
    const values = Object.create(null) as Record<string, string>
    await act(async () => root.render(<SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="mapping-sample"
      items={[{ key: '__proto__', label: '__proto__', type: 'text' }]} values={values} onChange={vi.fn()} onReset={onReset} emptyText="None" />))
    expect(document.querySelector<HTMLInputElement>('#mapping-sample-__proto__')?.value).toBe('')
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Dùng mẫu mặc định')!.click())
    expect(onReset).toHaveBeenCalledOnce()
  })
})

describe('inputSchemaPreviewFields', () => {
  it('maps template inputs to positional renderer field definitions', () => {
    expect(inputSchemaPreviewFields([{ key: 'Word', type: 'text' }, { key: 'Audio', type: 'audio' }])).toEqual([
      { id: 'f_0', name: 'Word', field_type: 'text', position: 0 },
      { id: 'f_1', name: 'Audio', field_type: 'audio', position: 1 },
    ])
  })
})

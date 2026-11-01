// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SampleValuesSheet } from './SampleValuesSheet'
import { inputSchemaPreviewFields } from '../lib/previewFields'
import { useState } from 'react'
import type { TemplateSampleValues } from '../model/previewSamples'

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

  it('shows editable type-specific defaults and playable media instead of placeholders', async () => {
    const onChange = vi.fn()
    await act(async () => root.render(<SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="sample"
      items={items} values={{ Word: 'neko' }} onChange={onChange} onReset={vi.fn()} />))
    const word = document.querySelector<HTMLInputElement>('#sample-Word')!
    expect(word.tagName).toBe('INPUT')
    expect(word.value).toBe('neko')
    const meaning = document.querySelector<HTMLTextAreaElement>('#sample-Meaning')!
    expect(meaning.tagName).toBe('TEXTAREA')
    expect(meaning.value).toContain('## Sample heading')
    expect(document.querySelector<HTMLInputElement>('#sample-Audio')?.value).toBe('/store/sample-audio.mp3')
    expect(document.querySelector('audio')?.getAttribute('src')).toContain('/store/sample-audio.mp3')
    // Only explicit samples are marked as overrides.
    expect(document.body.textContent?.match(/Mẫu tùy chỉnh/g)).toHaveLength(1)

    await type(meaning, 'con mèo')
    expect(onChange).toHaveBeenLastCalledWith('Meaning', 'con mèo')
    await act(async () => document.querySelector<HTMLButtonElement>('[aria-label="Để trống Phát âm"]')!.click())
    expect(onChange).toHaveBeenLastCalledWith('Audio', '')
  })

  it('does not mistake inherited values for samples and resets through the callback', async () => {
    const onReset = vi.fn()
    const values = Object.create(null) as Record<string, string>
    await act(async () => root.render(<SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="mapping-sample"
      items={[{ key: '__proto__', label: '__proto__', type: 'text' }]} values={values} onChange={vi.fn()} onReset={onReset} emptyText="None" />))
    expect(document.querySelector<HTMLInputElement>('#mapping-sample-__proto__')?.value).toBe('Sample text')
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'Dùng mẫu mặc định')!.click())
    expect(onReset).toHaveBeenCalledOnce()
  })

  it('edits native array items, reorders and clears them, and retains invalid JSON without sending it', async () => {
    const onChange = vi.fn()
    function Editor() {
      const [values, setValues] = useState<TemplateSampleValues>({})
      return <SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="sample" items={[{ key: 'options', label: 'Options', type: 'array' }]}
        values={values} onChange={(key, value) => { onChange(key, value); setValues((old) => ({ ...old, [key]: value })) }} onReset={() => setValues({})} />
    }
    await act(async () => root.render(<Editor />))
    await type(document.querySelector<HTMLInputElement>('#sample-options')!, 'First')
    expect(onChange).toHaveBeenLastCalledWith('options', ['First', 'Second item', 'Third item'])
    await act(async () => document.querySelector<HTMLButtonElement>('[aria-label="Đưa phần tử 1 xuống"]')!.click())
    expect(onChange).toHaveBeenLastCalledWith('options', ['Second item', 'First', 'Third item'])
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'JSON nâng cao')!.click())
    const code = document.querySelector<HTMLTextAreaElement>('#sample-options')!
    onChange.mockClear()
    await type(code, '[1]')
    expect(onChange).not.toHaveBeenCalled()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('JSON list')
    await type(code, '["one",["two",""]]')
    expect(onChange).toHaveBeenLastCalledWith('options', ['one', ['two', '']])
    await act(async () => document.querySelector<HTMLButtonElement>('[aria-label="Để trống Options"]')!.click())
    expect(onChange).toHaveBeenLastCalledWith('options', [])
    await act(async () => document.querySelector<HTMLButtonElement>('[aria-label="Khôi phục mẫu Options"]')!.click())
    expect(onChange).toHaveBeenLastCalledWith('options', ['First item', 'Second item', 'Third item'])
  })

  it('edits rich text visually and strips active markup from the sample', async () => {
    const onChange = vi.fn()
    await act(async () => root.render(<SampleValuesSheet open onOpenChange={vi.fn()} title="Samples" description="Preview only" idPrefix="sample"
      items={[{ key: 'rich', label: 'Rich', type: 'richtext' }]} values={{}} onChange={onChange} onReset={vi.fn()} />))
    const editor = document.querySelector<HTMLDivElement>('#sample-rich')!
    expect(editor.getAttribute('contenteditable')).toBe('true')
    expect(editor.querySelector('strong')?.textContent).toBe('Sample text')
    await act(async () => {
      editor.innerHTML = '<p><strong>Safe</strong><img src="x" onerror="alert(1)"></p>'
      editor.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(onChange).toHaveBeenLastCalledWith('rich', '<p><strong>Safe</strong></p>')
    expect(editor.querySelector('img')).toBeNull()
    await act(async () => { editor.innerHTML = '<p><br></p>'; editor.dispatchEvent(new Event('input', { bubbles: true })) })
    expect(onChange).toHaveBeenLastCalledWith('rich', '')
    await act(async () => [...document.querySelectorAll('button')].find((button) => button.textContent === 'HTML nâng cao')!.click())
    expect(document.querySelector('#sample-rich')?.tagName).toBe('TEXTAREA')
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

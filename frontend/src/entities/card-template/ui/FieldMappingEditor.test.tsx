// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { validateBindings, type MappingField, type MappingInput } from '../lib/fieldMapping'
import { FieldMappingEditor } from './FieldMappingEditor'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
const inputs: MappingInput[] = [{ key: 'Word', label: 'Từ', type: 'text', required: true }, { key: 'word', label: 'Từ khác', type: 'text', required: false }]
const fields: MappingField[] = [{ id: 'field-text', name: 'Word', field_type: 'text' }, { id: 'field-image', name: 'Picture', field_type: 'image' }]

describe('FieldMappingEditor', () => {
  it('shows a nonblocking warning for a selected mismatched field', async () => {
    const bindings = { Word: 'field-image', word: null }
    await act(async () => root.render(<FieldMappingEditor inputs={inputs} fields={fields} bindings={bindings} onChange={vi.fn()} issues={validateBindings(inputs, fields, bindings)} />))
    const select = container.querySelector('select')!
    expect(select.value).toBe('field-image')
    expect(select.getAttribute('aria-invalid')).toBe('false')
    expect(container.textContent).toContain('Dữ liệu vẫn được truyền')
  })
  let root: Root
  let container: HTMLDivElement
  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(() => { act(() => root.unmount()); container.remove() })
  it('emits a new stable ID mapping, then null when unbound', async () => {
    const bindings = Object.freeze({ Word: null, word: 'field-text' })
    const onChange = vi.fn()
    await act(async () => root.render(<FieldMappingEditor inputs={inputs} fields={fields} bindings={bindings} onChange={onChange} issues={validateBindings(inputs, fields, bindings)} />))
    const select = container.querySelector('select')!
    expect(select.getAttribute('aria-invalid')).toBe('false')
    expect(container.textContent).toContain('Khuyến nghị')
    expect(container.textContent).toContain('vẫn có thể sử dụng')
    await act(async () => { select.value = 'field-text'; select.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(onChange).toHaveBeenLastCalledWith({ Word: 'field-text', word: 'field-text' })
    expect(bindings.Word).toBeNull()
    await act(async () => { select.value = ''; select.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(onChange).toHaveBeenLastCalledWith({ Word: null, word: 'field-text' })
  })
  it('allows other types, retains stale value and shows scope error', async () => {
    const bindings = { Word: 'foreign', word: null }
    await act(async () => root.render(<FieldMappingEditor inputs={inputs} fields={fields} bindings={bindings} onChange={vi.fn()} issues={validateBindings(inputs, fields, bindings)} />))
    const select = container.querySelector('select')!
    expect(select.value).toBe('foreign')
    expect(select.querySelector<HTMLOptionElement>('option[value="field-image"]')?.disabled).toBe(false)
    expect(select.getAttribute('aria-invalid')).toBe('true')
    expect(container.textContent).toContain('Trường không thuộc loại thẻ đã chọn.')
    expect(container.textContent).toContain('Input này sẽ hiển thị rỗng.')
  })
  it('disables editing and permits removing an obsolete schema mapping', async () => {
    const onChange = vi.fn()
    const bindings = { Word: 'field-text', word: 'field-text', obsolete: null }
    const props = { inputs, fields, bindings, onChange, issues: validateBindings(inputs, fields, bindings) }
    await act(async () => root.render(<FieldMappingEditor {...props} disabled />))
    expect(Array.from(container.querySelectorAll('select')).every((select) => select.disabled)).toBe(true)
    expect(container.querySelector('button')!.disabled).toBe(true)
    await act(async () => root.render(<FieldMappingEditor {...props} />))
    await act(async () => container.querySelector('button')!.click())
    expect(onChange).toHaveBeenCalledWith({ Word: 'field-text', word: 'field-text' })
  })
  it('shows omitted prototype-named keys as empty and emits an own __proto__ binding', async () => {
    const keys = ['__proto__', 'constructor', 'toString']
    const prototypeInputs: MappingInput[] = keys.map((key) => ({ key, label: key, type: 'text', required: false }))
    const onChange = vi.fn()
    await act(async () => root.render(<FieldMappingEditor inputs={prototypeInputs} fields={fields} bindings={{}} onChange={onChange}
      issues={validateBindings(prototypeInputs, fields, {})} />))
    expect(Array.from(container.querySelectorAll('select')).map((select) => select.value)).toEqual(['', '', ''])
    expect(container.textContent).not.toContain('Trường không còn tồn tại')
    await act(async () => {
      const select = container.querySelector('select')!
      select.value = 'field-text'; select.dispatchEvent(new Event('change', { bubbles: true }))
    })
    const next = onChange.mock.calls[0][0]
    expect(Object.hasOwn(next, '__proto__')).toBe(true)
    expect(next.__proto__).toBe('field-text')
    expect(Object.getPrototypeOf(next)).toBe(Object.prototype)
  })
})

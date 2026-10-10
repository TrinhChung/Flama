// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TemplateInputSpec } from '@/entities/card-template'
import { TemplateInputSchemaEditor } from './TemplateInputSchemaEditor'

describe('TemplateInputSchemaEditor', () => {
  let root: Root
  let container: HTMLDivElement
  const change = vi.fn()
  const value: TemplateInputSpec[] = [{ key: 'Input1', label: 'First', type: 'text', required: true }]
  beforeEach(() => { vi.clearAllMocks(); container = document.createElement('div'); document.body.append(container); root = createRoot(container) })
  afterEach(async () => { await act(async () => root.unmount()); container.remove() })
  async function render(disabled = false) { await act(async () => root.render(<TemplateInputSchemaEditor value={value} onChange={change} disabled={disabled} />)) }
  async function select() { await act(async () => container.querySelector<HTMLButtonElement>('[aria-pressed="false"]')!.click()) }
  it('uses all exact types, advisory required wording and immutable add/delete', async () => {
    await render(); expect(container.querySelector('select')).toBeNull(); await select(); expect([...container.querySelectorAll('option')].map((el) => el.value)).toEqual(['text', 'richtext', 'markdown', 'image', 'audio', 'diagram', 'answers'])
    expect(container.textContent).toContain('Khuyến nghị ánh xạ'); expect(container.textContent).toContain('Dữ liệu mà thiết kế thẻ cần nhận.')
    await act(async () => [...container.querySelectorAll('button')].find((el) => el.textContent === 'Thêm input')!.click())
    expect(change).toHaveBeenLastCalledWith([...value, { key: 'Input2', label: '', type: 'text', required: false }]); expect(value).toHaveLength(1)
    await select(); await act(async () => [...container.querySelectorAll('button')].find((el) => el.textContent?.trim() === 'Xóa input')!.click()); expect(change).toHaveBeenLastCalledWith([]); expect(value).toHaveLength(1)
  })
  it('allows an invalid key draft and clones the changed item', async () => {
    await render(); await select(); const input = container.querySelector<HTMLInputElement>('details input')!
    await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, ' bad '); input.dispatchEvent(new Event('input', { bubbles: true })) })
    expect(change).toHaveBeenCalledWith([{ ...value[0], key: ' bad ' }]); expect(change.mock.calls[0][0][0]).not.toBe(value[0]); expect(value[0].key).toBe('Input1')
  })
  it('switches to an answers input without typing options and drops saved ones', async () => {
    await render(); await select(); const select_ = container.querySelector<HTMLSelectElement>('select')!
    await act(async () => { select_.value = 'answers'; select_.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(change).toHaveBeenLastCalledWith([{ ...value[0], type: 'answers' }])
    const saved: TemplateInputSpec[] = [{ ...value[0], type: 'answers', typing: { show_length: true, hints: true } }]
    await act(async () => root.render(<TemplateInputSchemaEditor value={saved} onChange={change} />))
    expect(container.textContent).not.toContain('Chế độ gõ')
    await act(async () => { select_.value = 'text'; select_.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(change).toHaveBeenLastCalledWith([value[0]])
  })
  // Parked 2026-10-10 with the host typing mode (STUDY_TYPING_ANSWER_PLAN §12).
  it.skip('switches to a typed-answer input with typing options', async () => {
    await render(); await select(); const select_ = container.querySelector<HTMLSelectElement>('select')!
    await act(async () => { select_.value = 'answers'; select_.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(change).toHaveBeenLastCalledWith([{ ...value[0], type: 'answers', typing: { show_length: true, hints: true } }])
    const answers: TemplateInputSpec[] = [{ ...value[0], type: 'answers', typing: { show_length: true, hints: true } }]
    await act(async () => root.render(<TemplateInputSchemaEditor value={answers} onChange={change} />))
    expect(container.textContent).toContain('Chế độ gõ')
    const hints = [...container.querySelectorAll<HTMLInputElement>('fieldset input[type="checkbox"]')][1]
    await act(async () => hints.click())
    expect(change).toHaveBeenLastCalledWith([{ ...answers[0], typing: { show_length: true, hints: false } }])
  })
  it('disables every editing control without mutations', async () => {
    await render(true); expect([...container.querySelectorAll('button')].every((el) => el.disabled)).toBe(true)
    await act(async () => [...container.querySelectorAll('button')].forEach((el) => el.click())); expect(change).not.toHaveBeenCalled()
  })
})

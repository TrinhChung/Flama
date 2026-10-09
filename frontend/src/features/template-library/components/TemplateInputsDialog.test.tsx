// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TemplateInputsDialog } from './TemplateInputsDialog'

const value = [{ key: 'Word', label: 'Word label', type: 'text' as const, required: true }]
const button = (label: string) => [...document.querySelectorAll('button')].find((item) => item.textContent?.trim() === label)!
async function text(element: HTMLInputElement, next: string) { await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, next); element.dispatchEvent(new Event('input', { bubbles: true })) }) }
describe('TemplateInputsDialog local draft lifecycle', () => {
  let root: Root
  let container: HTMLDivElement
  const apply = vi.fn()
  const close = vi.fn()
  beforeEach(async () => { vi.clearAllMocks(); container = document.createElement('div'); document.body.append(container); root = createRoot(container); await act(async () => root.render(<TemplateInputsDialog open onOpenChange={close} value={value} persistedKeys={['Word']} onApply={apply} frontHtml="{{#Word}}{{Word}}{{/Word}}" backHtml="" applicationCount={2} />)) })
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); document.body.innerHTML = '' })
  async function select() { await act(async () => document.querySelector<HTMLButtonElement>('[aria-pressed="false"]')!.click()) }
  it('shows a single selected input form, keeps saved keys read-only and prevents deleting a used token', async () => {
    expect(document.querySelector('select')).toBeNull(); await select()
    expect(document.querySelector<HTMLInputElement>('details input')?.readOnly).toBe(true)
    expect(button('Xóa input').disabled).toBe(true)
    expect(document.body.textContent).toContain('Xóa token của input ở Mặt trước')
  })
  it('cancel discards the modal draft without applying changes to the workspace', async () => {
    await select(); const input = document.querySelector<HTMLInputElement>('input[maxlength="255"]')!; await text(input, 'Updated label')
    expect(apply).not.toHaveBeenCalled(); expect(value[0].label).toBe('Word label')
    await act(async () => button('Hủy').click()); expect(close).toHaveBeenCalledWith(false); expect(apply).not.toHaveBeenCalled()
  })
  it('applies inputs into the workspace draft only when explicitly requested', async () => {
    await select(); await text(document.querySelector<HTMLInputElement>('input[maxlength="255"]')!, 'Updated label')
    await act(async () => button('Áp dụng vào bản nháp').click())
    expect(apply).toHaveBeenCalledWith([{ ...value[0], label: 'Updated label' }]); expect(close).toHaveBeenCalledWith(false)
  })
  it('asks to keep or discard changes when dismissed with Escape', async () => {
    await select(); await text(document.querySelector<HTMLInputElement>('input[maxlength="255"]')!, 'Updated label')
    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true })))
    expect(document.body.textContent).toContain('Bỏ thay đổi inputs?'); expect(close).not.toHaveBeenCalled()
    await act(async () => button('Tiếp tục chỉnh sửa').click()); expect(close).not.toHaveBeenCalled()
    await act(async () => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))); await act(async () => button('Bỏ thay đổi').click()); expect(close).toHaveBeenCalledWith(false)
  })
})

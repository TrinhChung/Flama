// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ArrayFieldInput } from './ArrayFieldInput'

describe('ArrayFieldInput', () => {
  let container: HTMLDivElement | null = null

  afterEach(() => {
    container?.remove()
    container = null
    document.body.replaceChildren()
  })

  async function renderComponent(props: Partial<React.ComponentProps<typeof ArrayFieldInput>> = {}) {
    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onChange = vi.fn()
    await act(async () => {
      root.render(
        <ArrayFieldInput
          fieldName="Collocation"
          value={props.value ?? 'item 1\nitem 2'}
          onChange={props.onChange ?? onChange}
          mode={props.mode}
          {...props}
        />,
      )
    })
    return { container, onChange }
  }

  it('renders normal view with lines by default', async () => {
    const { container: view } = await renderComponent({ value: 'apple\nbanana' })
    const textarea = view.querySelector('textarea')
    expect(textarea).not.toBeNull()
    expect(textarea?.value).toBe('apple\nbanana')
  })

  it('renders formatted JSON array code when mode is code without syntax error', async () => {
    const { container: view } = await renderComponent({ value: 'apple\nbanana', mode: 'code' })
    const textarea = view.querySelector('textarea')
    expect(textarea).not.toBeNull()
    expect(textarea?.value).toBe('[\n  "apple",\n  "banana"\n]')
    expect(view.textContent).not.toContain('Cú pháp JSON Array không hợp lệ')
  })

  it('switches between normal mode, code mode, and preview mode on button click', async () => {
    const onChange = vi.fn()
    const { container: view } = await renderComponent({ value: 'item 1\nitem 2', onChange })
    const buttons = view.querySelectorAll('button')
    // buttons: [preview (Eye), normal (AlignLeft), code (Code2)]
    expect(buttons.length).toBeGreaterThanOrEqual(3)
    const previewBtn = buttons[0]
    const normalBtn = buttons[1]
    const codeBtn = buttons[2]

    // Switch to code mode
    await act(async () => {
      codeBtn?.click()
    })

    const textarea = view.querySelector('textarea')
    expect(textarea?.value).toBe('[\n  "item 1",\n  "item 2"\n]')
    expect(onChange).toHaveBeenCalledWith('[\n  "item 1",\n  "item 2"\n]')
    expect(view.textContent).not.toContain('Cú pháp JSON Array không hợp lệ')

    // Switch to preview mode
    await act(async () => {
      previewBtn?.click()
    })
    expect(view.textContent).toContain('item 1')
    expect(view.textContent).toContain('item 2')

    // Switch back to normal mode
    await act(async () => {
      normalBtn?.click()
    })

    const textareaBack = view.querySelector('textarea')
    expect(textareaBack?.value).toBe('item 1\nitem 2')
    expect(onChange).toHaveBeenCalledWith('item 1\nitem 2')
  })

  it('handles bracket-prefixed values like [n] noun without syntax error when switching to code', async () => {
    const onChange = vi.fn()
    const { container: view } = await renderComponent({ value: '[n] con mèo\n[v] bắt chuột', onChange })
    const buttons = view.querySelectorAll('button')
    const codeBtn = buttons[2]

    await act(async () => {
      codeBtn?.click()
    })

    const textarea = view.querySelector('textarea')
    expect(textarea?.value).toBe('[\n  "[n] con mèo",\n  "[v] bắt chuột"\n]')
    expect(view.textContent).not.toContain('Cú pháp JSON Array không hợp lệ')
  })

  it('shows error warning only when invalid JSON is manually entered in code mode', async () => {
    const { container: view } = await renderComponent({ value: '["broken json', mode: 'code' })
    const textarea = view.querySelector('textarea')
    expect(textarea?.value).toBe('[\n  "[\\"broken json"\n]')

    // Manually type broken JSON into code textarea
    await act(async () => {
      if (textarea) {
        const nativeSetter = Object.getOwnPropertyDescriptor(
          window.HTMLTextAreaElement.prototype,
          'value',
        )?.set
        nativeSetter?.call(textarea, '["broken json')
        textarea.dispatchEvent(new Event('input', { bubbles: true }))
        textarea.dispatchEvent(new Event('change', { bubbles: true }))
      }
    })

    // Should show error message
    const error = view.textContent
    expect(error).toContain('JSON Array')
  })
})

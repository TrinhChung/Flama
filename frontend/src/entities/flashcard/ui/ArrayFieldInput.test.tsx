// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ArrayFieldInput } from './ArrayFieldInput'

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('ArrayFieldInput', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  afterEach(() => {
    act(() => root?.unmount())
    root = null
    container?.remove()
    container = null
    document.body.replaceChildren()
  })

  async function renderComponent(props: Partial<React.ComponentProps<typeof ArrayFieldInput>> = {}) {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
    const onChange = vi.fn()
    await act(async () => {
      root!.render(
        <ArrayFieldInput
          fieldName="Collocation"
          value={props.value ?? 'item 1\nitem 2'}
          onChange={props.onChange ?? onChange}
          mode={props.mode}
          {...props}
        />,
      )
    })
    return { container, onChange, root: root! }
  }

  it('renders normal view with lines by default', async () => {
    const { container: view } = await renderComponent({ value: 'apple\nbanana' })
    const textarea = view.querySelector('textarea')
    expect(textarea).not.toBeNull()
    expect(textarea?.value).toBe('apple\nbanana')
  })

  it('shows server-escaped characters as typed in lines and preview, but keeps code as stored', async () => {
    const value = ['R&amp;D', '1 &lt; 2 -&gt; 3', '&lt;b&gt; literal', 'a&amp;nbsp;b']
    const { container: view } = await renderComponent({ value })
    expect(view.querySelector('textarea')?.value).toBe('R&D\n1 < 2 -> 3\n&lt;b> literal\na&amp;nbsp;b')
    act(() => root?.unmount())
    const preview = await renderComponent({ value, mode: 'preview' })
    expect(preview.container.textContent).toContain('R&D')
    act(() => root?.unmount())
    const code = await renderComponent({ value, mode: 'code' })
    expect(code.container.querySelector('textarea')?.value).toContain('"R&amp;D"')
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
    expect(onChange).not.toHaveBeenCalled()
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
    expect(onChange).not.toHaveBeenCalled()
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
    expect(error).toContain('Cú pháp JSON Array không hợp lệ')
    expect(textarea?.getAttribute('aria-invalid')).toBe('true')
  })

  it('keeps nested arrays intact through preview and code without reporting an edit', async () => {
    const value = [['a', 'b'], ['c'], '', 'a']
    const { container: view, onChange } = await renderComponent({ value })
    expect(JSON.parse(view.querySelector('textarea')!.value)).toEqual(value)
    expect(view.querySelector<HTMLButtonElement>('[aria-label="Nhập thường Collocation"]')!.disabled).toBe(true)
    await act(async () => view.querySelector<HTMLButtonElement>('[aria-label="Xem trước Collocation"]')!.click())
    await act(async () => view.querySelector<HTMLButtonElement>('[aria-label="Xem code Collocation"]')!.click())
    expect(JSON.parse(view.querySelector('textarea')!.value)).toEqual(value)
    expect(onChange).not.toHaveBeenCalled()
  })

  it('reports invalid JSON content and prevents switching away from the broken draft', async () => {
    const onValidityChange = vi.fn()
    const { container: view } = await renderComponent({ mode: 'code', onValidityChange })
    const textarea = view.querySelector('textarea')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, '[1, null]')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(onValidityChange).toHaveBeenLastCalledWith(false)
    expect(view.querySelector<HTMLButtonElement>('[aria-label="Nhập thường Collocation"]')!.disabled).toBe(true)
    expect(view.querySelector<HTMLButtonElement>('[aria-label="Xem trước Collocation"]')!.disabled).toBe(true)
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!.call(textarea, '[["a"], "b"]')
      textarea.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(onValidityChange).toHaveBeenLastCalledWith(true)
  })

  it('updates presentation when a controlled mode changes and when values are reverted', async () => {
    const value = ['a', 'b']
    const { container: view, root: renderedRoot, onChange } = await renderComponent({ value })
    await act(async () => renderedRoot.render(<ArrayFieldInput fieldName="Collocation" value={value} mode="code" onChange={onChange} />))
    expect(JSON.parse(view.querySelector('textarea')!.value)).toEqual(value)
    await act(async () => renderedRoot.render(<ArrayFieldInput fieldName="Collocation" value={['original']} mode="code" onChange={onChange} />))
    expect(JSON.parse(view.querySelector('textarea')!.value)).toEqual(['original'])
    expect(onChange).not.toHaveBeenCalled()
  })

  it('keeps an invalid nested-array draft in Code even when the controlled mode requests Normal', async () => {
    const onValidityChange = vi.fn()
    const { container: view } = await renderComponent({ value: [['nested']], mode: 'normal', onValidityChange })
    const input = view.querySelector('textarea')!
    await act(async () => {
      Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')!.set!.call(input, '["broken"')
      input.dispatchEvent(new Event('input', { bubbles: true }))
    })
    expect(input.value).toBe('["broken"')
    expect(input.getAttribute('aria-invalid')).toBe('true')
    expect(onValidityChange).toHaveBeenLastCalledWith(false)
  })
})

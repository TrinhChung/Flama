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

  it('renders formatted JSON array code when mode is code', async () => {
    const { container: view } = await renderComponent({ value: 'apple\nbanana', mode: 'code' })
    const textarea = view.querySelector('textarea')
    expect(textarea).not.toBeNull()
    expect(textarea?.value).toBe('[\n  "apple",\n  "banana"\n]')
  })

  it('switches between normal mode and code mode on button click', async () => {
    const onChange = vi.fn()
    const { container: view } = await renderComponent({ value: 'item 1\nitem 2', onChange })
    const button = view.querySelector('button')
    expect(button).not.toBeNull()

    // Switch to code mode
    await act(async () => {
      button?.click()
    })

    const textarea = view.querySelector('textarea')
    expect(textarea?.value).toBe('[\n  "item 1",\n  "item 2"\n]')
    expect(onChange).toHaveBeenCalledWith('[\n  "item 1",\n  "item 2"\n]')

    // Switch back to normal mode
    await act(async () => {
      button?.click()
    })

    expect(textarea?.value).toBe('item 1\nitem 2')
    expect(onChange).toHaveBeenCalledWith('item 1\nitem 2')
  })

  it('shows error warning when invalid JSON is entered in code mode', async () => {
    const { container: view } = await renderComponent({ value: '["broken json', mode: 'code' })
    const textarea = view.querySelector('textarea')
    expect(textarea?.value).toBe('["broken json')
    // Should show error message
    const error = view.textContent
    expect(error).toContain('JSON Array')
  })
})

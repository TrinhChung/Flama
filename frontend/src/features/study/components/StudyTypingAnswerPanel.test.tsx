// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { StudyTypingAnswerPanel, type StudyTypingAnswerPanelProps } from './StudyTypingAnswerPanel'

describe('StudyTypingAnswerPanel', () => {
  let root: Root
  let container: HTMLDivElement
  const onReveal = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
  })

  const props = (overrides: Partial<StudyTypingAnswerPanelProps> = {}): StudyTypingAnswerPanelProps => ({
    answers: ['食べる', 'たべる'],
    showLength: true,
    hints: true,
    revealed: false,
    onReveal,
    ...overrides,
  })
  async function render(overrides: Partial<StudyTypingAnswerPanelProps> = {}) {
    await act(async () => root.render(<StudyTypingAnswerPanel {...props(overrides)} />))
  }
  const input = () => container.querySelector<HTMLInputElement>('input')!
  async function type(value: string) {
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input(), value)
      input().dispatchEvent(new Event('input', { bubbles: true }))
    })
  }
  async function pressEnter(init: KeyboardEventInit = {}) {
    const event = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, ...init })
    await act(async () => { input().dispatchEvent(event) })
    return event
  }
  const button = (label: string) => [...container.querySelectorAll('button')].find((el) => el.textContent?.includes(label))!

  it('flips the card on a correct answer and consumes the Enter key', async () => {
    await render()
    await type('たべる')
    const event = await pressEnter()
    expect(event.defaultPrevented).toBe(true)
    expect(onReveal).toHaveBeenCalledTimes(1)
  })

  it('reports an incorrect answer, keeps the card and lets the learner retype', async () => {
    await render()
    await type('タベル')
    await pressEnter()
    expect(onReveal).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Chưa đúng, gõ lại nhé.')
    expect(container.textContent).not.toContain('食べる ·')
    await type('食べ')
    expect(container.textContent).not.toContain('Chưa đúng, gõ lại nhé.')
  })

  it('ignores the Enter that confirms an IME conversion', async () => {
    await render()
    await type('たべる')
    const event = await pressEnter({ isComposing: true })
    expect(event.defaultPrevented).toBe(false)
    expect(onReveal).not.toHaveBeenCalled()
  })

  it('shows the answer length and reveals hint characters up to one short', async () => {
    await render()
    expect(container.textContent).toContain('3 ký tự')
    const hint = button('Gợi ý')
    await act(async () => hint.click())
    expect(container.textContent).toContain('食')
    expect(container.textContent).toContain('1/2')
    await act(async () => hint.click())
    expect(hint.disabled).toBe(true)
  })

  it('hides the length but still shows revealed hints when the template asks', async () => {
    await render({ showLength: false })
    expect(container.textContent).not.toContain('ký tự')
    await act(async () => button('Gợi ý').click())
    expect(container.textContent).toContain('食…')
  })

  it('skips to the back and summarizes the attempt', async () => {
    await render()
    await type('sai')
    await pressEnter()
    await act(async () => button('Bỏ qua').click())
    expect(onReveal).toHaveBeenCalledTimes(1)
    await render({ revealed: true })
    expect(container.textContent).toContain('Đã bỏ qua · 1 lần gõ sai')
    expect(container.textContent).toContain('Bạn gõ: sai')
    expect(container.textContent).toContain('Đáp án: 食べる · たべる')
    expect(container.querySelector('input')).toBeNull()
  })

  it('summarizes a correct answer after retries and hints', async () => {
    await render()
    await act(async () => button('Gợi ý').click())
    await type('sai')
    await pressEnter()
    await type('食べる')
    await pressEnter()
    await render({ revealed: true })
    expect(container.textContent).toContain('Đúng · lần thử thứ 2 · đã mở 1 gợi ý')
    expect(container.textContent).not.toContain('Bạn gõ')
  })

  it('shows only the answers for a card restored already flipped', async () => {
    await render({ revealed: true })
    expect(container.textContent).not.toContain('Đã bỏ qua')
    expect(container.textContent).toContain('Đáp án: 食べる · たべる')
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CardPreviewPanel } from './CardPreviewPanel'

const display = vi.hoisted(() => vi.fn())
vi.mock('./CardDisplay', () => ({ CardDisplay: display }))
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('CardPreviewPanel', () => {
  let root: Root
  let container: HTMLDivElement
  beforeEach(() => {
    display.mockReset()
    display.mockImplementation(({ side }: { side: string }) => <div data-testid="card-display">{side}</div>)
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    document.body.replaceChildren()
  })
  const viewport = () => container.querySelector<HTMLElement>('[data-slot="card-preview-viewport"]')!
  const sideButton = (label: string) => [...container.querySelectorAll<HTMLButtonElement>('[role="group"] button')].find((button) => button.textContent?.trim() === label)!

  it('renders the card on an absolute layer so percentage heights resolve inside any parent', async () => {
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontPayload={{ html: 'front' }} backPayload={{ html: 'back' }} />))
    const layer = viewport().firstElementChild!
    expect(layer.className).toBe('absolute inset-3')
    expect(layer.querySelector('[data-testid="card-display"]')).not.toBeNull()
    // Without `fill`, the viewport keeps its own height and may grow inside a stretched card.
    expect(viewport().className).toContain('flex-auto')
    expect(viewport().className).toContain('h-[clamp(14rem,40vh,30rem)]')
  })

  it('fills the parent on large screens and keeps a screen-relative height below lg', async () => {
    await act(async () => root.render(<CardPreviewPanel fill cardId="c1" frontHtml="front" containerHeightClass="h-40" />))
    const card = container.querySelector('[data-slot="card"]')!
    expect(card.className).toContain('h-full')
    expect(viewport().className).toContain('lg:flex-1')
    expect(viewport().className).toContain('h-[60svh]')
    expect(viewport().className).not.toContain('h-40')
  })

  it('switches sides internally or through the controlled callback', async () => {
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontHtml="front" backHtml="back" />))
    expect(sideButton('Mặt trước').getAttribute('aria-pressed')).toBe('true')
    await act(async () => sideButton('Mặt sau').click())
    expect(display).toHaveBeenLastCalledWith(expect.objectContaining({ side: 'back' }), undefined)
    expect(sideButton('Mặt sau').getAttribute('aria-pressed')).toBe('true')

    const onSideChange = vi.fn()
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontHtml="front" side="front" onSideChange={onSideChange} />))
    await act(async () => sideButton('Mặt sau').click())
    expect(onSideChange).toHaveBeenCalledWith('back')
    expect(sideButton('Mặt trước').getAttribute('aria-pressed')).toBe('true')
  })

  it('shows header actions, errors and the preparing state without mounting the renderer', async () => {
    await act(async () => root.render(<CardPreviewPanel cardId="c1" headerActions={<button type="button">Samples</button>} />))
    expect(container.textContent).toContain('Samples')
    expect(container.textContent).toContain('Đang chuẩn bị bản xem trước…')
    expect(display).not.toHaveBeenCalled()
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontHtml="front" error="Template failed" />))
    expect(container.querySelector('[role="alert"]')?.textContent).toBe('Template failed')
    expect(display).not.toHaveBeenCalled()
  })

  it('offers a template picker only when there is a choice', async () => {
    const onSelectTemplate = vi.fn()
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontHtml="front" templates={[{ id: 't1', name: 'Card 1' }]} onSelectTemplate={onSelectTemplate} />))
    expect(container.querySelector('select')).toBeNull()
    await act(async () => root.render(<CardPreviewPanel cardId="c1" frontHtml="front" templates={[{ id: 't1', name: 'Card 1' }, { id: 't2', name: 'Card 2' }]} selectedTemplateId="t2" onSelectTemplate={onSelectTemplate} />))
    const select = container.querySelector('select')!
    expect(select.value).toBe('t2')
    await act(async () => { select.value = 't1'; select.dispatchEvent(new Event('change', { bubbles: true })) })
    expect(onSelectTemplate).toHaveBeenCalledWith('t1')
  })
})

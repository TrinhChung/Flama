// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useNearViewport } from './useNearViewport'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function Probe({ eager = false }: { eager?: boolean }) {
  const { ref, near, height } = useNearViewport<HTMLDivElement>('10px', eager)
  return <div ref={ref} data-near={String(near)} data-height={String(height)} />
}

describe('useNearViewport', () => {
  let root: Root
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
    vi.unstubAllGlobals()
  })

  it('treats everything as near without IntersectionObserver', async () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    await act(async () => root.render(<Probe />))
    expect(container.firstElementChild?.getAttribute('data-near')).toBe('true')
  })

  it('follows observations and keeps the height an element had when it left', async () => {
    let notify: (entries: Partial<IntersectionObserverEntry>[]) => void = () => {}
    const observed: Element[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(callback: (entries: Partial<IntersectionObserverEntry>[]) => void) { notify = callback }
      observe(element: Element) { observed.push(element) }
      unobserve() {}
      disconnect() {}
    })
    await act(async () => root.render(<Probe />))
    const element = container.firstElementChild!
    expect(element.getAttribute('data-near')).toBe('false')
    await act(async () => notify([{ target: observed[0], isIntersecting: true, boundingClientRect: { height: 0 } as DOMRectReadOnly }]))
    expect(element.getAttribute('data-near')).toBe('true')
    await act(async () => notify([{ target: observed[0], isIntersecting: false, boundingClientRect: { height: 240 } as DOMRectReadOnly }]))
    expect(element.getAttribute('data-near')).toBe('false')
    expect(element.getAttribute('data-height')).toBe('240')
  })
})

// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { Spinner } from './spinner'

describe('Spinner component', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    const currentRoot = root
    if (currentRoot) {
      act(() => {
        currentRoot.unmount()
      })
    }
    if (container && container.parentNode) {
      container.parentNode.removeChild(container)
    }
    container = null
    root = null
  })

  it('renders with role="status" and accessibility text', async () => {
    await act(async () => {
      root?.render(<Spinner />)
    })

    const statusEl = container?.querySelector('[role="status"]')
    expect(statusEl).not.toBeNull()
    expect(statusEl?.textContent).toContain('Đang tải...')
  })

  it('applies custom size and class names correctly', async () => {
    await act(async () => {
      root?.render(<Spinner size="lg" className="my-custom-spinner" />)
    })

    const statusEl = container?.querySelector('[role="status"]')
    expect(statusEl?.className).toContain('my-custom-spinner')

    const svgEl = container?.querySelector('svg')
    const svgClasses = svgEl?.getAttribute('class') || ''
    expect(svgClasses).toContain('size-8')
    expect(svgClasses).toContain('animate-spin')
  })
})

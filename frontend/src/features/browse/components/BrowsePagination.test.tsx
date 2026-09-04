// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { BrowsePagination } from './BrowsePagination'

describe('BrowsePagination', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  it('renders nothing when total is 0', async () => {
    const setPage = vi.fn()
    const handlePerPageChange = vi.fn()

    await act(async () => {
      root.render(
        <BrowsePagination
          page={1}
          setPage={setPage}
          perPage={20}
          handlePerPageChange={handlePerPageChange}
          total={0}
          pages={0}
        />,
      )
    })

    expect(container.innerHTML).toBe('')
  })

  it('renders range, total cards count, and selection count', async () => {
    const setPage = vi.fn()
    const handlePerPageChange = vi.fn()

    await act(async () => {
      root.render(
        <BrowsePagination
          page={2}
          setPage={setPage}
          perPage={20}
          handlePerPageChange={handlePerPageChange}
          total={55}
          pages={3}
          selectedCount={4}
        />,
      )
    })

    // StartItem = (2-1)*20 + 1 = 21, endItem = min(40, 55) = 40
    expect(container.textContent).toContain('21–40')
    expect(container.textContent).toContain('55')
    expect(container.textContent).toContain('4 đã chọn')
  })

  it('triggers handlePerPageChange when per-page dropdown item is clicked', async () => {
    const setPage = vi.fn()
    const handlePerPageChange = vi.fn()

    await act(async () => {
      root.render(
        <BrowsePagination
          page={1}
          setPage={setPage}
          perPage={20}
          handlePerPageChange={handlePerPageChange}
          total={100}
          pages={5}
        />,
      )
    })

    const trigger = container.querySelector(
      'button[aria-label="Chọn số dòng trên một trang"]',
    ) as HTMLButtonElement
    expect(trigger).not.toBeNull()
    expect(trigger.textContent).toContain('20 dòng')

    await act(async () => {
      trigger.focus()
      trigger.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
      trigger.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })

    const option50 = Array.from(document.body.querySelectorAll('[role="menuitem"]')).find(
      (el) => el.textContent?.includes('50'),
    ) as HTMLElement
    expect(option50).toBeDefined()

    await act(async () => {
      option50.click()
    })

    expect(handlePerPageChange).toHaveBeenCalledWith(50)
  })

  it('navigates to next, previous, first, and last pages', async () => {
    const setPage = vi.fn()
    const handlePerPageChange = vi.fn()

    await act(async () => {
      root.render(
        <BrowsePagination
          page={3}
          setPage={setPage}
          perPage={20}
          handlePerPageChange={handlePerPageChange}
          total={100}
          pages={5}
        />,
      )
    })

    // Find first page button
    const firstBtn = container.querySelector('button[title^="Trang đầu"]') as HTMLButtonElement
    expect(firstBtn).toBeDefined()
    await act(async () => {
      firstBtn.click()
    })
    expect(setPage).toHaveBeenCalledWith(1)

    // Find last page button
    const lastBtn = container.querySelector('button[title^="Trang cuối"]') as HTMLButtonElement
    expect(lastBtn).toBeDefined()
    await act(async () => {
      lastBtn.click()
    })
    expect(setPage).toHaveBeenCalledWith(5)
  })

  it('supports jump to page submission when pages >= 6', async () => {
    const setPage = vi.fn()
    const handlePerPageChange = vi.fn()

    await act(async () => {
      root.render(
        <BrowsePagination
          page={1}
          setPage={setPage}
          perPage={20}
          handlePerPageChange={handlePerPageChange}
          total={200}
          pages={10}
        />,
      )
    })

    const jumpInput = container.querySelector('input[type="number"]') as HTMLInputElement
    expect(jumpInput).not.toBeNull()

    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value',
      )?.set
      nativeSetter?.call(jumpInput, '7')
      jumpInput.dispatchEvent(new Event('input', { bubbles: true }))
      jumpInput.dispatchEvent(new Event('change', { bubbles: true }))
    })

    const form = jumpInput.closest('form')
    await act(async () => {
      form?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    })

    expect(setPage).toHaveBeenCalledWith(7)
  })
})

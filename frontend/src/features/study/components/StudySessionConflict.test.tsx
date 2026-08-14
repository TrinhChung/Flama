// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudySessionConflict } from './StudySessionConflict'

describe('StudySessionConflict', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('offers a safe handoff or leaving the current tab', async () => {
    const onTakeover = vi.fn()
    const onLeave = vi.fn()
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StudySessionConflict
          deckName="N5"
          takeoverState="idle"
          onTakeover={onTakeover}
          onLeave={onLeave}
        />,
      )
    })

    const title = container.querySelector('h1')
    expect(title?.textContent).toContain('Deck này đang được học ở tab khác')
    expect(document.activeElement).toBe(title)
    expect(container.textContent).toContain('Dữ liệu đã lưu vẫn được giữ nguyên')
    const buttons = Array.from(container.querySelectorAll('button'))

    await act(async () => buttons.find((button) => (
      button.textContent?.includes('Chuyển phiên sang tab này')
    ))?.click())
    await act(async () => buttons.find((button) => (
      button.textContent?.includes('Rời phiên ở tab này')
    ))?.click())

    expect(onTakeover).toHaveBeenCalledOnce()
    expect(onLeave).toHaveBeenCalledOnce()

    await act(async () => root.unmount())
  })

  it('offers a safe retry after the other tab stops responding', async () => {
    const onTakeover = vi.fn()
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StudySessionConflict
          takeoverState="unavailable"
          onTakeover={onTakeover}
          onLeave={vi.fn()}
        />,
      )
    })

    const retryButton = Array.from(container.querySelectorAll('button')).find(
      (button) => button.textContent?.includes('Gửi lại yêu cầu'),
    )
    const warning = container.querySelector('[role="alert"]')
    expect(retryButton).toBeDefined()
    expect(warning?.textContent).toContain('Khi tab kia đóng')
    await act(async () => retryButton?.click())

    expect(onTakeover).toHaveBeenCalledOnce()

    await act(async () => root.unmount())
  })
})

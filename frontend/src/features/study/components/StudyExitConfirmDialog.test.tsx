// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyExitConfirmDialog } from './StudyExitConfirmDialog'

describe('StudyExitConfirmDialog', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders confirmation dialog with event counts and handles Save & Exit', async () => {
    const onSaveAndExit = vi.fn()
    const onContinueStudy = vi.fn()
    const onDiscardAndExit = vi.fn()
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StudyExitConfirmDialog
          open={true}
          eventsCount={15}
          isCommitting={false}
          onSaveAndExit={onSaveAndExit}
          onContinueStudy={onContinueStudy}
          onDiscardAndExit={onDiscardAndExit}
        />,
      )
    })

    expect(document.body.textContent).toContain('Kết thúc phiên học?')
    expect(document.body.textContent).toContain('15 thẻ')
    expect(document.body.textContent).toContain('Lưu & Thoát')

    const saveButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Lưu & Thoát'),
    )
    expect(saveButton).toBeDefined()
    await act(async () => saveButton?.click())

    expect(onSaveAndExit).toHaveBeenCalledOnce()

    await act(async () => root.unmount())
  })

  it('handles Continue Study and Discard & Exit actions', async () => {
    const onSaveAndExit = vi.fn()
    const onContinueStudy = vi.fn()
    const onDiscardAndExit = vi.fn()
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <StudyExitConfirmDialog
          open={true}
          eventsCount={5}
          isCommitting={false}
          onSaveAndExit={onSaveAndExit}
          onContinueStudy={onContinueStudy}
          onDiscardAndExit={onDiscardAndExit}
        />,
      )
    })

    const continueButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Tiếp tục học'),
    )
    await act(async () => continueButton?.click())
    expect(onContinueStudy).toHaveBeenCalledOnce()

    const discardButton = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('Thoát không lưu tiến độ này'),
    )
    await act(async () => discardButton?.click())
    expect(onDiscardAndExit).toHaveBeenCalledOnce()

    await act(async () => root.unmount())
  })
})
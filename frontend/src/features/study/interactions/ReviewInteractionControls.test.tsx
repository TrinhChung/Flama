// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReviewInteractionControls } from './ReviewInteractionControls'

describe('ReviewInteractionControls', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders reveal button when card is not revealed', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onReveal = vi.fn()

    await act(async () => {
      root.render(
        <ReviewInteractionControls
          revealed={false}
          onReveal={onReveal}
        />,
      )
    })

    expect(container.textContent).toContain('Hiện đáp án')

    const button = container.querySelector('button')
    expect(button).not.toBeNull()
    await act(async () => {
      button?.click()
    })
    expect(onReveal).toHaveBeenCalledTimes(1)

    await act(async () => root.unmount())
  })

  it('renders 4 rating buttons with preview labels and emits both onAnswer and onReviewAction', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onReveal = vi.fn()
    const onAnswer = vi.fn()
    const onReviewAction = vi.fn()

    const intervalsPreview = {
      again: { label: '<10m' },
      hard: { label: '1d' },
      good: { label: '3d' },
      easy: { label: '7d' },
    }

    await act(async () => {
      root.render(
        <ReviewInteractionControls
          revealed={true}
          intervalsPreview={intervalsPreview}
          onReveal={onReveal}
          onAnswer={onAnswer}
          onReviewAction={onReviewAction}
        />,
      )
    })

    expect(container.textContent).toContain('Học lại')
    expect(container.textContent).toContain('<10m')
    expect(container.textContent).toContain('Khó')
    expect(container.textContent).toContain('1d')
    expect(container.textContent).toContain('Tốt')
    expect(container.textContent).toContain('3d')
    expect(container.textContent).toContain('Dễ')
    expect(container.textContent).toContain('7d')

    const buttons = container.querySelectorAll('button')
    expect(buttons.length).toBe(4)

    // Click "Tốt" (Good, 3rd button)
    await act(async () => {
      buttons[2]?.click()
    })

    expect(onAnswer).toHaveBeenCalledWith('good')
    expect(onReviewAction).toHaveBeenCalledWith({
      rating: 'good',
      actionKey: 'review.good',
      triggerKey: 'scheduler.review.good',
      triggerContractVersion: '1',
    })

    await act(async () => root.unmount())
  })
})

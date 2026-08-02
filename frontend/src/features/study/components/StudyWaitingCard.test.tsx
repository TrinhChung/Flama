// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyWaitingCard } from './StudyWaitingCard'

describe('StudyWaitingCard', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('labels pending learning as waiting instead of completion', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const now = Date.parse('2026-02-22T09:00:00.000Z')

    await act(async () => {
      root.render(
        <MemoryRouter>
          <StudyWaitingCard
            deckName="N5"
            counts={{ new: 0, learning: 3, due: 0 }}
            nowMs={now}
            pendingLearningCount={3}
            nextEligibleAtMs={now + 300_000}
            nextDueAtMs={now + 600_000}
            isBusy={false}
            onCommit={vi.fn()}
          />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Đang chờ lượt học lại')
    expect(container.textContent).toContain('Còn 3 thẻ chờ learning step')
    expect(container.textContent).toContain('Tiếp tục sau 5 phút 00 giây')
    expect(container.textContent).not.toContain('Hoàn thành')

    await act(async () => root.unmount())
  })
})

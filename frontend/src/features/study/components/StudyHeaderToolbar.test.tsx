// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StudyHeaderToolbar } from './StudyHeaderToolbar'

describe('StudyHeaderToolbar', () => {
  afterEach(() => {
    document.body.replaceChildren()
  })

  it('renders navigation links, deck name, and queue counter badges', async () => {
    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const onEdit = vi.fn()

    await act(async () => {
      root.render(
        <MemoryRouter>
          <StudyHeaderToolbar
            deckName="Từ vựng N2"
            deckId="42"
            cardId="card-10"
            canEdit={true}
            onEdit={onEdit}
            newCount={15}
            learnCount={4}
            dueCount={28}
          />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Decks')
    expect(container.textContent).toContain('Study')
    expect(container.textContent).toContain('Stats')
    expect(container.textContent).toContain('Từ vựng N2')
    expect(container.textContent).toContain('Mới 15')
    expect(container.textContent).toContain('Học 4')
    expect(container.textContent).toContain('Hạn 28')
    expect(container.textContent).toContain('Sửa thẻ')

    const editButton = Array.from(container.querySelectorAll('button')).find(
      (btn) => btn.textContent?.includes('Sửa thẻ') || btn.getAttribute('aria-label')?.includes('Sửa nhanh thẻ'),
    )
    expect(editButton).toBeDefined()

    await act(async () => {
      editButton?.click()
    })
    expect(onEdit).toHaveBeenCalledTimes(1)

    await act(async () => root.unmount())
  })
})

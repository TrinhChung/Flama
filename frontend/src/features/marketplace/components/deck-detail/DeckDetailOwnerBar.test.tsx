// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DeckDetailOwnerBar } from './DeckDetailOwnerBar'

describe('DeckDetailOwnerBar UX', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
  })

  it('renders private warning banner and "Công khai lên Marketplace" button when listing is new draft', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <DeckDetailOwnerBar
            id="item-test-1"
            publishStatus="private"
            publishedAt={null}
            currentReleaseId={null}
            showKeyManager={false}
            setShowKeyManager={vi.fn()}
            onUpdatePublishStatus={vi.fn()}
            isPublishStatusPending={false}
            autoPublishMutation={{ mutate: vi.fn(), isPending: false }}
          />
        </MemoryRouter>
      )
    })

    // Expect private warning banner to be visible
    expect(container.textContent).toContain('Bộ thẻ đang ở chế độ Riêng tư (Bản nháp)')
    expect(container.textContent).toContain('Chỉ bạn mới có thể xem trang này')

    // Expect button to say "Công khai lên Marketplace" (not "Xuất bản lại")
    expect(container.textContent).toContain('Công khai lên Marketplace')
    expect(container.textContent).not.toContain('Xuất bản lại')
  })

  it('renders "Xuất bản lại" button when listing was previously published and revoked', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <DeckDetailOwnerBar
            id="item-test-2"
            publishStatus="private"
            publishedAt="2026-10-31T12:00:00"
            currentReleaseId="release-123"
            showKeyManager={false}
            setShowKeyManager={vi.fn()}
            onUpdatePublishStatus={vi.fn()}
            isPublishStatusPending={false}
            autoPublishMutation={{ mutate: vi.fn(), isPending: false }}
          />
        </MemoryRouter>
      )
    })

    // Warning banner is still visible because it's private
    expect(container.textContent).toContain('Bộ thẻ đang ở chế độ Riêng tư (Bản nháp)')
    // But button says "Xuất bản lại"
    expect(container.textContent).toContain('Xuất bản lại')
  })

  it('renders "Thu hồi bộ deck" and no private banner when listing is published', async () => {
    await act(async () => {
      root.render(
        <MemoryRouter>
          <DeckDetailOwnerBar
            id="item-test-3"
            publishStatus="published"
            publishedAt="2026-10-31T12:00:00"
            currentReleaseId="release-123"
            showKeyManager={false}
            setShowKeyManager={vi.fn()}
            onUpdatePublishStatus={vi.fn()}
            isPublishStatusPending={false}
            autoPublishMutation={{ mutate: vi.fn(), isPending: false }}
          />
        </MemoryRouter>
      )
    })

    // No private warning banner
    expect(container.textContent).not.toContain('Bộ thẻ đang ở chế độ Riêng tư (Bản nháp)')
    // Revoke button
    expect(container.textContent).toContain('Thu hồi bộ deck')
  })
})

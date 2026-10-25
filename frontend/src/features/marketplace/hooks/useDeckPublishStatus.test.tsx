// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import '@/shared/config/i18n'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import { apiJson } from '@/shared/api/client'
import { useDeckPublishStatus } from './useDeckPublishStatus'

vi.mock('@/shared/api/client', () => ({ apiJson: vi.fn() }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

let mutation: ReturnType<typeof useDeckPublishStatus>
function Probe() {
  mutation = useDeckPublishStatus('item-1')
  return null
}
async function settle() { await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) }) }

describe('Deck listing publish status', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient
  beforeEach(async () => {
    vi.clearAllMocks()
    client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    await act(async () => root.render(<QueryClientProvider client={client}><Probe /></QueryClientProvider>))
  })
  afterEach(async () => { await act(async () => root.unmount()); client.clear(); container.remove() })

  it.each(['private', 'published'] as const)('patches the listing to %s', async (status) => {
    vi.mocked(apiJson).mockResolvedValue({ id: 'item-1', publish_status: status })
    await act(async () => mutation.mutate(status))
    await settle()
    expect(apiJson).toHaveBeenCalledWith('/api/shared/decks/item-1', 'PATCH', { publish_status: status })
    expect(toast.success).toHaveBeenCalledTimes(1)
  })

  it('shows the server reason when the listing cannot change', async () => {
    vi.mocked(apiJson).mockRejectedValue(new Error('Description is required for publish.'))
    await act(async () => mutation.mutate('published'))
    await settle()
    expect(toast.error).toHaveBeenCalledWith('Description is required for publish.')
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

;(globalThis as typeof globalThis & {
  IS_REACT_ACT_ENVIRONMENT: boolean
}).IS_REACT_ACT_ENVIRONMENT = true

vi.mock('@/app/api', () => ({
  appApi: {
    get: vi.fn().mockResolvedValue({}),
    generateStrokes: vi.fn().mockResolvedValue({ characters: [], items: [], output: '' }),
    estimateBatchStrokes: vi.fn().mockResolvedValue({}),
    batchGenerateStrokes: vi.fn().mockResolvedValue({ updated: 0, skipped: 0 }),
  },
}))

import { BrowseStrokeModal } from './BrowseStrokeModal'

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  container = document.createElement('div')
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  if (root && container) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
})

describe('BrowseStrokeModal', () => {
  it('renders without throwing when browse prop is undefined and cardId is undefined', () => {
    expect(() => {
      act(() => {
        root?.render(
          <QueryClientProvider client={queryClient}>
            <BrowseStrokeModal
              isOpen={false}
              onClose={() => {}}
              mode="single"
            />
          </QueryClientProvider>,
        )
      })
    }).not.toThrow()
  })

  it('renders open dialog cleanly without browse or cardDetailQuery', () => {
    expect(() => {
      act(() => {
        root?.render(
          <QueryClientProvider client={queryClient}>
            <BrowseStrokeModal
              isOpen={true}
              onClose={() => {}}
              mode="single"
              cardId="card-999"
              fields={[
                { name: 'Word', field_type: 'text' },
                { name: 'StrokeDiagram', field_type: 'diagram' },
              ]}
              fieldValues={{ Word: '漢字' }}
            />
          </QueryClientProvider>,
        )
      })
    }).not.toThrow()

    expect(document.body.textContent).toContain('Tạo sơ đồ thứ tự nét Kanji & Hanzi')
  })
})

// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiRequest } from '@/shared/api/client'
import { fetchTemplateApplications } from '@/entities/card-template'
import { NoteTypeTemplatesPage } from './NoteTypeTemplatesPage'

vi.mock('@/shared/api/client', () => ({ apiRequest: vi.fn() }))
vi.mock('@/entities/card-template', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/entities/card-template')>(),
  fetchTemplateApplications: vi.fn(),
}))
vi.mock('@/features/template-library', () => ({
  TemplateApplicationsPanel: ({ noteTypeId }: { noteTypeId: string }) => <div data-testid="applications">{noteTypeId}</div>,
  AttachTemplateDialog: ({ open, onApplied }: { open: boolean; onApplied: (value: { id: string }) => void }) =>
    open ? <button data-testid="apply-template" onClick={() => onApplied({ id: 'real-occurrence' })}>Apply</button> : null,
}))

function Location() {
  return <output data-testid="location">{useLocation().pathname}</output>
}

describe('NoteTypeTemplatesPage', () => {
  let container: HTMLDivElement
  let root: Root
  let client: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(apiRequest).mockResolvedValue({ id: 'nt-1', name: 'Owned NoteType', field_defs: [] })
    vi.mocked(fetchTemplateApplications).mockResolvedValue({ schema_version: 'template-applications.v2', items: [] })
    client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    client.clear()
    container.remove()
  })

  async function renderPage() {
    await act(async () => {
      root.render(<QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/flashcards/note-types/nt-1/templates']}>
          <Location />
          <Routes>
            <Route path="/flashcards/note-types/:id/templates" element={<NoteTypeTemplatesPage />} />
            <Route path="/flashcards/note-types/:id/templates/:applicationId" element={<div>Mapping editor</div>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>)
    })
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }

  it('shows the real note type without a fabricated release warning or update action', async () => {
    await renderPage()
    expect(container.querySelector('[data-testid="applications"]')?.textContent).toBe('nt-1')
    expect(container.textContent).toContain('Owned NoteType')
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.textContent).not.toContain('v1.1.0')
    expect(apiRequest).toHaveBeenCalledWith('/api/note-types/nt-1', expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(fetchTemplateApplications).toHaveBeenCalledWith('nt-1', true, expect.any(AbortSignal))
  })

  it('opens attachment and navigates to the actual occurrence returned by the API', async () => {
    await renderPage()
    const attach = Array.from(container.querySelectorAll('button')).find((button) => button.querySelector('.lucide-plus'))
    expect(attach).toBeDefined()
    await act(async () => attach!.click())
    const apply = container.querySelector<HTMLButtonElement>('[data-testid="apply-template"]')
    expect(apply).not.toBeNull()
    await act(async () => apply!.click())
    expect(container.querySelector('[data-testid="location"]')?.textContent)
      .toBe('/flashcards/note-types/nt-1/templates/real-occurrence')
  })
})

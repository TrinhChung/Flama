// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { comparison } = vi.hoisted(() => ({ comparison: vi.fn() }))
vi.mock('@/features/deck-collaboration', () => ({
  BaseOverrideComparisonView: ({ installId }: { installId: string }) => {
    comparison(installId)
    return <div>Personal changes for {installId}</div>
  },
}))
import { InstalledDeckComparisonPage } from './index'

function Location() {
  return <output>{useLocation().pathname}</output>
}

describe('installed deck comparison routes', () => {
  let root: Root
  let container: HTMLDivElement
  beforeEach(() => {
    comparison.mockClear()
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })
  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
  })
  async function render(path: string) {
    await act(async () => root.render(
      <MemoryRouter initialEntries={[path]}>
        <Location />
        <Routes>
          <Route path="/installed-decks/:installId/comparison" element={<InstalledDeckComparisonPage />} />
          <Route path="/installed-decks/:installId/updates/:releaseId" element={<InstalledDeckComparisonPage />} />
        </Routes>
      </MemoryRouter>,
    ))
  }
  it('opens personal comparison directly without asking for legacy update status', async () => {
    await render('/installed-decks/install-1/comparison')
    expect(comparison).toHaveBeenCalledWith('install-1')
    expect(container.textContent).toContain('Personal changes for install-1')
  })
  it('redirects old update URLs to comparison and drops the obsolete release', async () => {
    await render('/installed-decks/install-1/updates/old-release')
    expect(container.querySelector('output')?.textContent).toBe('/installed-decks/install-1/comparison')
    expect(comparison).toHaveBeenCalledWith('install-1')
  })
})

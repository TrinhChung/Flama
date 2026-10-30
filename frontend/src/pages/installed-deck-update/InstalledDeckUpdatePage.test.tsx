// @vitest-environment jsdom
import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
const { useMode, baseView, legacyView } = vi.hoisted(() => ({
  useMode: vi.fn(), baseView: vi.fn(), legacyView: vi.fn(),
}))
vi.mock('@/features/deck-collaboration', () => ({
  useInstalledDeckContentModel: useMode,
  BaseOverrideComparisonView: ({ installId }: { installId: string }) => { baseView(installId); return <div>Personal comparison</div> },
  InstalledDeckUpdateLegacyPage: () => { legacyView(); return <div>Legacy update</div> },
}))
import { InstalledDeckUpdatePage } from './index'
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let cleanup = () => {}
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('installed deck route content model', () => {
  async function render(mode: 'published_base' | undefined, path: string) {
    useMode.mockReturnValue({ data: { content_model: mode }, isPending: false, error: null })
    const host = document.createElement('div'); document.body.append(host)
    const root = createRoot(host)
    cleanup = () => { act(() => root.unmount()); host.remove() }
    await act(async () => root.render(<MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/installed-decks/:installId/comparison" element={<InstalledDeckUpdatePage />} />
      <Route path="/installed-decks/:installId/updates/:releaseId" element={<InstalledDeckUpdatePage />} />
    </Routes></MemoryRouter>))
    return host
  }
  it('uses personal comparison for both new route and old release links after cutover', async () => {
    const host = await render('published_base', '/installed-decks/install-1/updates/old-release')
    expect(host.textContent).toContain('Personal comparison')
    expect(baseView).toHaveBeenCalledWith('install-1')
    expect(legacyView).not.toHaveBeenCalled()
  })
  it('keeps the existing update workflow when the rollout flag is off', async () => {
    const host = await render(undefined, '/installed-decks/install-1/updates/release-1')
    expect(host.textContent).toContain('Legacy update')
    expect(baseView).not.toHaveBeenCalled()
  })
  it('opens the comparison without a historical release id', async () => {
    const host = await render('published_base', '/installed-decks/install-1/comparison')
    expect(host.textContent).toContain('Personal comparison')
  })
})

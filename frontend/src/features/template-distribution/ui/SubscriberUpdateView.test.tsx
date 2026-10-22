// @vitest-environment jsdom
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SubscriberUpdateView } from './SubscriberUpdateView'
import { useSubscriberUpdateView } from '../hooks/useSubscriberUpdateView'

const store = vi.hoisted(() => ({ result: {} as Record<string, unknown> }))
vi.mock('../hooks/useTemplateSubscription', () => ({ useTemplateSubscription: () => store.result }))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))
vi.mock('react-i18next', async (importOriginal) => ({
  ...await importOriginal<typeof import('react-i18next')>(),
  useTranslation: () => ({ t: (key: string) => key, i18n: { language: 'en' } }),
}))

describe('legacy received template update controls', () => {
  let root: Root
  let container: HTMLDivElement
  const settings = vi.fn()
  const prepare = vi.fn()
  const apply = vi.fn()
  const reset = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    store.result = {
      subscription: {
        id: null, source_template_id: 'original/source', applied_release_id: null,
        applied_release: null, current_release: { id: 'release-current', version_label: '2.0.0', sequence_no: 2 },
        legacy_unpinned: true, requires_new_canonical_receipt: true, last_sync_status: 'legacy_unpinned',
        // Even stale or inconsistent update flags must not enable a merge without a known base.
        update_available: true, auto_update_enabled: true,
      },
      isLoading: false, isError: false, updateSettings: settings, prepareUpdate: prepare,
      applyUpdate: apply, resetToUpstream: reset, refetch: vi.fn(),
    }
    container = document.createElement('div')
    document.body.append(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    container.remove()
  })

  async function renderView() {
    await act(async () => root.render(<MemoryRouter><SubscriberUpdateView templateId="old-copy" /></MemoryRouter>))
  }

  it('keeps personal content distinct from a new receipt and disables destructive update controls', async () => {
    await renderView()
    expect(container.textContent).toContain('distribution.legacy_unpinned.version_unknown')
    expect(container.textContent).toContain('distribution.legacy_unpinned.preserved')
    expect(container.textContent).toContain('distribution.legacy_unpinned.receive_separately')
    expect(container.textContent).not.toContain('distribution.original_release')
    expect(container.querySelector('a')?.getAttribute('href')).toBe('/marketplace/templates/original%2Fsource')
    const controls = [...container.querySelectorAll<HTMLButtonElement>('button')]
    const update = controls.find((button) => button.textContent?.includes('distribution.btn_update'))!
    const restore = controls.find((button) => button.textContent?.includes('distribution.btn_reset_upstream'))!
    const automatic = container.querySelector<HTMLButtonElement>('[role="switch"]')!
    for (const control of [update, restore, automatic]) {
      expect(control.disabled).toBe(true)
      await act(async () => control.click())
    }
    expect(automatic.getAttribute('aria-checked')).toBe('false')
    expect(settings).not.toHaveBeenCalled()
    expect(prepare).not.toHaveBeenCalled()
    expect(apply).not.toHaveBeenCalled()
    expect(reset).not.toHaveBeenCalled()
  })

  it('shows an unknown source without constructing a guessed original link', async () => {
    store.result.subscription = { ...(store.result.subscription as object), source_template_id: null }
    await renderView()
    expect(container.querySelector('a')).toBeNull()
    expect(container.textContent).toContain('distribution.legacy_unpinned.version_unknown')
  })

  it('guards mutation handlers even when invoked without clicking a disabled button', async () => {
    let handlers: ReturnType<typeof useSubscriberUpdateView> | undefined
    function Probe() {
      handlers = useSubscriberUpdateView({ templateId: 'old-copy' })
      return null
    }
    await act(async () => root.render(<Probe />))
    await act(async () => {
      await handlers!.handleToggleAutoUpdate(true)
      await handlers!.handleStartUpdate()
      await handlers!.handleResetToUpstream()
      await handlers!.handleApplyResolvedUpdate({})
      handlers!.handleResetOpenChange(true)
    })
    expect(handlers!.resetConfirmOpen).toBe(false)
    for (const mutation of [settings, prepare, apply, reset]) expect(mutation).not.toHaveBeenCalled()
  })

  it('retains update and automatic settings for a normally pinned receipt', async () => {
    store.result.subscription = {
      ...(store.result.subscription as object), legacy_unpinned: false, requires_new_canonical_receipt: false,
      applied_release_id: 'release-old', applied_release: { version_label: '1.0.0', sequence_no: 1 },
      last_sync_status: 'ready', auto_update_enabled: false,
    }
    prepare.mockResolvedValue({ id: 'preparation', status: 'ready', conflicts: {} })
    await renderView()
    expect(container.textContent).not.toContain('distribution.legacy_unpinned.title')
    const automatic = container.querySelector<HTMLButtonElement>('[role="switch"]')!
    const update = [...container.querySelectorAll<HTMLButtonElement>('button')]
      .find((button) => button.textContent?.includes('distribution.btn_update'))!
    expect(automatic.disabled).toBe(false)
    expect(update.disabled).toBe(false)
    await act(async () => automatic.click())
    await act(async () => update.click())
    expect(settings).toHaveBeenCalledWith({ auto_update_enabled: true })
    expect(prepare).toHaveBeenCalledWith(expect.objectContaining({ release_id: 'release-current', expected_applied_release_id: 'release-old' }))
    expect(apply).toHaveBeenCalledWith({ preparation_id: 'preparation' })
  })
})

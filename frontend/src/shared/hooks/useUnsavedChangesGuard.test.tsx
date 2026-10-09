// @vitest-environment jsdom
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import { useUnsavedChangesGuard } from './useUnsavedChangesGuard'

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('unsaved draft navigation', () => {
  let root: Root
  let container: HTMLDivElement
  const save = vi.fn<() => Promise<void>>()
  const discard = vi.fn()
  const destination = vi.fn()
  const flush = () => act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
  const find = (label: string) => Array.from(document.querySelectorAll('button')).find((button) => button.textContent === label)!
  const click = async (label: string) => { await act(async () => find(label).click()); await flush() }
  function Editor() {
    const guard = useUnsavedChangesGuard(true, 'An unfinished field', { onSave: save, onDiscard: discard })
    return <><button onClick={() => guard.requestNavigation(destination)}>Next field</button>{guard.confirmDialog}</>
  }
  beforeEach(async () => {
    await i18n.changeLanguage('en')
    save.mockReset().mockResolvedValue(undefined); discard.mockReset(); destination.mockReset()
    container = document.createElement('div'); document.body.append(container); root = createRoot(container)
    await act(async () => root.render(<MemoryRouter><Editor /></MemoryRouter>))
  })
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); document.body.innerHTML = '' })

  it('waits for a successful save and never invokes the discard callback on that path', async () => {
    let finish: () => void = () => undefined
    save.mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve }))
    await click('Next field'); await click('Save and continue')
    expect(destination).not.toHaveBeenCalled()
    expect(find('Continue editing').disabled).toBe(true)
    await act(async () => finish()); await flush()
    expect(destination).toHaveBeenCalledOnce()
    expect(discard).not.toHaveBeenCalled()
  })

  it('retains the pending choice on save failure and clears its old error when reopened', async () => {
    save.mockRejectedValueOnce(new Error('Connection lost'))
    await click('Next field'); await click('Save and continue')
    expect(document.querySelector('[role="alert"]')?.textContent).toBe('Connection lost')
    expect(destination).not.toHaveBeenCalled()
    await click('Continue editing'); await click('Next field')
    expect(document.querySelector('[role="alert"]')).toBeNull()
    await click('Save and continue')
    expect(destination).toHaveBeenCalledOnce()
    expect(discard).not.toHaveBeenCalled()
  })

  it('keeps the draft when staying and explicitly discards before proceeding', async () => {
    find('Next field').focus()
    await click('Next field'); await click('Continue editing')
    expect(discard).not.toHaveBeenCalled()
    expect(destination).not.toHaveBeenCalled()
    expect(document.activeElement).toBe(find('Next field'))
    await click('Next field'); await click('Discard and continue')
    expect(discard).toHaveBeenCalledOnce()
    expect(destination).toHaveBeenCalledOnce()
    expect(save).not.toHaveBeenCalled()
  })
})

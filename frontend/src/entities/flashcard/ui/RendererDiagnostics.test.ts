// @vitest-environment jsdom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('sandbox diagnostic boundary', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
  })

  function mountHost() {
    window.eval(readFileSync(resolve(process.cwd(), '../static/js/card_renderer_host.js'), 'utf8'))
    const iframe = document.createElement('iframe')
    document.body.append(iframe)
    const onError = vi.fn()
    const onReady = vi.fn()
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe, { onError, onReady, readyTimeoutMs: 500 })
    const render = (hash: string, side = 'front') => {
      controller.render({ html: '<p>candidate</p>' }, { config: { side }, context: { cardId: 'preview', candidateHash: hash } })
      return iframe.srcdoc.match(/"instanceId":"([^"]+)"/)![1]
    }
    const send = (instanceId: string, action: string, payload: unknown, source = iframe.contentWindow) => {
      window.dispatchEvent(new MessageEvent('message', {
        source, data: { channel: 'flama-card-renderer', direction: 'renderer_to_host', instanceId, action, payload },
      }))
    }
    return { iframe, controller, render, send, onError, onReady }
  }

  it('rejects spoofed sources and stale instances, uses host identity, and bounds errors', () => {
    const host = mountHost()
    const old = host.render('old')
    const current = host.render('current', 'back')
    host.send(old, 'log_error', { message: 'stale' })
    host.send(current, 'log_error', { message: 'spoofed' }, window)
    host.send(current, 'log_error', { message: { arbitrary: 'object' } })
    expect(host.onError).not.toHaveBeenCalled()
    for (let i = 0; i < 30; i++) {
      host.send(current, 'log_error', { message: 'x'.repeat(2000), candidateHash: 'spoofed', side: 'front' })
    }
    expect(host.onError).toHaveBeenCalledTimes(20)
    expect(host.onError).toHaveBeenCalledWith({
      code: 'SANDBOX_RUNTIME_ERROR', stage: 'runtime', message: 'x'.repeat(1000), side: 'back', cardId: 'preview', candidateHash: 'current',
    })
    expect(host.iframe.getAttribute('sandbox')).toBe('allow-scripts')
    host.controller.destroy()
  })

  it('reports readiness once and cancels ready timeouts on ready, replacement and destroy', () => {
    vi.useFakeTimers()
    const host = mountHost()
    const first = host.render('first')
    host.send(first, 'renderer_ready', { height: 240 })
    host.send(first, 'renderer_ready', { height: 240 })
    vi.advanceTimersByTime(700)
    expect(host.onReady).toHaveBeenCalledTimes(1)
    expect(host.onError).not.toHaveBeenCalled()
    host.render('second')
    vi.advanceTimersByTime(300)
    host.render('third', 'back')
    vi.advanceTimersByTime(300)
    expect(host.onError).not.toHaveBeenCalled()
    vi.advanceTimersByTime(200)
    expect(host.onError).toHaveBeenCalledWith(expect.objectContaining({ code: 'RENDERER_TIMEOUT', candidateHash: 'third', side: 'back', stage: 'host' }))
    host.render('fourth')
    host.controller.destroy()
    vi.advanceTimersByTime(700)
    expect(host.onError).toHaveBeenCalledTimes(1)
  })
})

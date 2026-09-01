// @vitest-environment jsdom
/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

describe('card renderer host viewport modes', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
  })

  it('preserves template viewport-height styles in fill-height mode', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { fillHeight: true },
    )

    controller.render(
      { html: '<div style="height:100vh">Centered card</div>' },
      { padding: '0' },
    )

    expect(iframe.style.height).toBe('100%')
    expect(iframe.srcdoc).toContain(
      '#flama-card-root { min-height: 100%; height: 100%;',
    )
    expect(iframe.srcdoc).not.toContain(
      '#flama-card-root [style*="height:100vh"]',
    )

    controller.destroy()
  })

  it('retains the viewport-height guard for auto-height embeds', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { autoHeight: true },
    )

    controller.render({ html: '<div style="height:100vh">Card</div>' })

    expect(iframe.style.height).toBe('180px')
    expect(iframe.srcdoc).toContain(
      '#flama-card-root [style*="height:100vh"]',
    )

    controller.destroy()
  })

  it('does not relay sandbox-authored keyboard events into host actions', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
    controller.render({ html: '<script>/* untrusted template */</script>' })

    const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
    const hostKeydown = vi.fn()
    window.addEventListener('keydown', hostKeydown)
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId,
        action: 'keydown_event',
        payload: { key: '3', code: 'Digit3' },
      },
    }))

    expect(hostKeydown).not.toHaveBeenCalled()
    expect(iframe.srcdoc).not.toContain("post('keydown_event'")
    expect(iframe.srcdoc).not.toContain("post('host_command'")
    window.removeEventListener('keydown', hostKeydown)

    const hostCommandHandler = vi.fn()
    window.addEventListener('flama:host-command', hostCommandHandler)
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId,
        action: 'host_command',
        payload: { command: 'rate_good' },
      },
    }))

    expect(hostCommandHandler).not.toHaveBeenCalled()
    window.removeEventListener('flama:host-command', hostCommandHandler)
    controller.destroy()
  })

  it('rejects postMessage payloads from unrelated windows, channels, or forged instanceIds', async () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
    controller.render({ html: '<div>Safe Card</div>' })

    const otherIframe = document.createElement('iframe')
    document.body.appendChild(otherIframe)

    const playSpy = vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    const hostCommandHandler = vi.fn()
    window.addEventListener('flama:host-command', hostCommandHandler)

    // 1. Message from unrelated window (wrong source Window)
    window.dispatchEvent(new MessageEvent('message', {
      source: otherIframe.contentWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId: 'forged-instance-id',
        action: 'host_command',
        payload: { command: 'rate_good' },
      },
    }))

    // 2. Message with invalid/wrong channel
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        channel: 'untrusted-channel',
        direction: 'renderer_to_host',
        instanceId: 'instance-id',
        action: 'host_command',
        payload: { command: 'rate_easy' },
      },
    }))

    // 3. Forged arbitrary action types
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId: 'instance-id',
        action: 'arbitrary_eval_or_rating',
        payload: { rating: 10, grant_permission: true },
      },
    }))

    expect(playSpy).not.toHaveBeenCalled()
    expect(hostCommandHandler).not.toHaveBeenCalled()

    window.removeEventListener('flama:host-command', hostCommandHandler)
    otherIframe.remove()
    controller.destroy()
  })

  it('relays shared audio results and ended events to the originating iframe element', async () => {
    vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    vi.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
    controller.render({
      html: '<audio id="voice" src="/media/proxy/audio-1"></audio>',
      allowed_media_urls: ['/media/proxy/audio-1'],
      allowed_audio_urls: ['/media/proxy/audio-1'],
    })

    const renderedDocument = new DOMParser().parseFromString(iframe.srcdoc, 'text/html')
    const sandboxShell = Array.from(renderedDocument.querySelectorAll('script'))
      .find((script) => script.textContent?.includes('initFlamaCardSandbox'))
    expect(sandboxShell).toBeTruthy()
    expect(() => new Function(sandboxShell!.textContent || '')).not.toThrow()

    const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
    expect(instanceId).toBeTruthy()
    const frameWindow = iframe.contentWindow!
    const postMessage = vi
      .spyOn(frameWindow, 'postMessage')
      .mockImplementation(() => undefined)
    const dispatchRendererMessage = (action: string, payload: Record<string, unknown>) => {
      window.dispatchEvent(new MessageEvent('message', {
        source: frameWindow,
        data: {
          channel: 'flama-card-renderer',
          direction: 'renderer_to_host',
          instanceId,
          action,
          payload,
        },
      }))
    }

    dispatchRendererMessage('renderer_ready', { height: 240 })
    dispatchRendererMessage('play_audio', {
      ref: '/media/proxy/audio-1',
      requestId: `${instanceId}:audio:1`,
      elementToken: 'flama-audio-1',
    })
    await Promise.resolve()

    expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1)
    expect(postMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'audio_result',
        payload: expect.objectContaining({ ok: true }),
      }),
      '*',
    )

    const sharedAudio = document.querySelector('body > audio[aria-hidden="true"]')
    expect(sharedAudio).toBeInstanceOf(window.HTMLAudioElement)
    sharedAudio!.dispatchEvent(new Event('ended'))
    expect(postMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        action: 'audio_event',
        payload: expect.objectContaining({
          type: 'ended',
          elementToken: 'flama-audio-1',
        }),
      }),
      '*',
    )

    controller.destroy()
  })

  it('resolves opaque media proxy ids against the configured backend origin', async () => {
    vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
    vi.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { mediaBaseUrl: 'https://be-flama.stmtp.com/' },
    )
    controller.render({
      html: '<img src="/media/proxy/image-1"><audio src="/media/proxy/audio-1"></audio>',
      allowed_media_urls: ['/media/proxy/image-1', '/media/proxy/audio-1'],
      allowed_audio_urls: ['/media/proxy/audio-1'],
    })

    expect(iframe.srcdoc).toContain('<base href="https://be-flama.stmtp.com/">')
    expect(iframe.srcdoc).toContain('base-uri https://be-flama.stmtp.com')
    expect(iframe.srcdoc).toContain('https://be-flama.stmtp.com/media/proxy/image-1')

    const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
    const frameWindow = iframe.contentWindow!
    window.dispatchEvent(new MessageEvent('message', {
      source: frameWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId,
        action: 'play_audio',
        payload: {
          ref: '/media/proxy/audio-1',
          requestId: `${instanceId}:audio:1`,
          elementToken: 'flama-audio-1',
        },
      },
    }))
    await Promise.resolve()

    const sharedAudio = document.querySelector('body > audio[aria-hidden="true"]')
    expect(sharedAudio?.getAttribute('src')).toBe(
      'https://be-flama.stmtp.com/media/proxy/audio-1',
    )
    controller.destroy()
  })

  it('adds exact public HTTPS media URLs to CSP without authorizing injected proxy ids', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
    controller.render({
      html: [
        '<img src="https://cdn.example.com/cards/cat.png">',
        '<audio src="https://cdn.example.com/audio/cat.mp3"></audio>',
        '<audio src="/media/proxy/not-attached"></audio>',
      ].join(''),
      allowed_media_urls: [
        'https://cdn.example.com/cards/cat.png',
        'https://cdn.example.com/audio/cat.mp3',
      ],
      allowed_audio_urls: ['https://cdn.example.com/audio/cat.mp3'],
    })

    expect(iframe.srcdoc).toContain('https://cdn.example.com/cards/cat.png')
    expect(iframe.srcdoc).toContain('https://cdn.example.com/audio/cat.mp3')
    expect(iframe.srcdoc).not.toContain(`${window.location.origin}/media/proxy/not-attached`)
    controller.destroy()
  })
})

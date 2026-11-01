// @vitest-environment jsdom
/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
// @ts-ignore
import { JSDOM } from 'jsdom'
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

  it('hands keyboard focus back to the page only while the frame holds it', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    iframe.tabIndex = 0
    document.body.appendChild(iframe)
    const outside = document.createElement('button')
    document.body.appendChild(outside)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
    controller.render({ html: '<div>Card</div>' })
    const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
    const releaseFocus = () => window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId,
        action: 'release_focus',
        payload: {},
      },
    }))

    iframe.focus()
    expect(document.activeElement).toBe(iframe)
    releaseFocus()
    expect(document.activeElement).toBe(document.body)

    outside.focus()
    releaseFocus()
    expect(document.activeElement).toBe(outside)
    controller.destroy()
  })

  describe('sandbox focus release after pointer clicks', () => {
    async function pointerUpIn(html: string, prepare: (doc: Document) => void) {
      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)
      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)
      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({ html })
      const sandbox = new JSDOM(iframe.srcdoc, { runScripts: 'dangerously' })
      const actions: string[] = []
      sandbox.window.addEventListener('message', (event: MessageEvent) => {
        actions.push(String(event.data?.action || ''))
      })
      prepare(sandbox.window.document)
      sandbox.window.document.body.dispatchEvent(
        new sandbox.window.Event('pointerup', { bubbles: true }),
      )
      await new Promise((resolve) => setTimeout(resolve, 30))
      controller.destroy()
      sandbox.window.close()
      return actions.filter((action) => action === 'release_focus')
    }

    it('asks to release focus after a click on card content or a template button', async () => {
      expect(await pointerUpIn('<p>水</p>', () => {})).toEqual(['release_focus'])
      expect(await pointerUpIn('<button id="hint">Hint</button>', (doc) => {
        doc.getElementById('hint')!.focus()
      })).toEqual(['release_focus'])
    })

    it('keeps focus in a template text field or an active text selection', async () => {
      expect(await pointerUpIn('<input id="answer">', (doc) => {
        doc.getElementById('answer')!.focus()
      })).toEqual([])
      expect(await pointerUpIn('<textarea id="note"></textarea>', (doc) => {
        doc.getElementById('note')!.focus()
      })).toEqual([])
      expect(await pointerUpIn('<p id="word">日本語</p>', (doc) => {
        const range = doc.createRange()
        range.selectNodeContents(doc.getElementById('word')!)
        const selection = doc.getSelection()!
        selection.removeAllRanges()
        selection.addRange(range)
      })).toEqual([])
    })
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
      { mediaBaseUrl: 'https://api.flama.vn/' },
    )
    controller.render({
      html: '<img src="/media/proxy/image-1"><audio src="/media/proxy/audio-1"></audio>',
      allowed_media_urls: ['/media/proxy/image-1', '/media/proxy/audio-1'],
      allowed_audio_urls: ['/media/proxy/audio-1'],
    })

    expect(iframe.srcdoc).toContain('<base href="https://api.flama.vn/">')
    expect(iframe.srcdoc).toContain('base-uri https://api.flama.vn')
    expect(iframe.srcdoc).toContain('https://api.flama.vn/media/proxy/image-1')

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
      'https://api.flama.vn/media/proxy/audio-1',
    )
    controller.destroy()
  })

  it('serves store media from the media origin and plays a legacy ref allowed under its store URL', async () => {
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
      { mediaBaseUrl: 'https://media.flama.vn/' },
    )
    controller.render({
      html: '<img src="/store/image-2.webp"><audio src="/media/proxy/audio-2"></audio><img src="/store/stroke_ja_4e00.svg">',
      allowed_media_urls: ['/store/image-2.webp', '/store/audio-2'],
      allowed_audio_urls: ['/store/audio-2'],
    })

    expect(iframe.srcdoc).toContain('<base href="https://media.flama.vn/">')
    expect(iframe.srcdoc).toContain('https://media.flama.vn/store/image-2.webp')
    expect(iframe.srcdoc).toContain('img-src https://media.flama.vn/store/image-2.webp https://media.flama.vn/store/audio-2 https://media.flama.vn/store/ ')

    const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
    window.dispatchEvent(new MessageEvent('message', {
      source: iframe.contentWindow!,
      data: {
        channel: 'flama-card-renderer',
        direction: 'renderer_to_host',
        instanceId,
        action: 'play_audio',
        payload: { ref: '/media/proxy/audio-2', requestId: `${instanceId}:audio:2`, elementToken: 'flama-audio-2' },
      },
    }))
    await Promise.resolve()

    const sharedAudio = document.querySelector('body > audio[aria-hidden="true"]')
    expect(sharedAudio?.getAttribute('src')).toBe('https://media.flama.vn/media/proxy/audio-2')
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

  it('derives proxy media from HTML when explicit allowed_media_urls is omitted and allows playback', async () => {
    vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockImplementation(() => Promise.resolve())
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
      { mediaBaseUrl: 'https://api.flama.vn/' },
    )
    controller.render({
      html: '<img src="/media/proxy/derived-img-1"><audio src="/media/proxy/derived-audio-1"></audio>',
    })

    expect(iframe.srcdoc).toContain('https://api.flama.vn/media/proxy/derived-img-1')
    expect(iframe.srcdoc).toContain('https://api.flama.vn/media/proxy/derived-audio-1')

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
          ref: '/media/proxy/derived-audio-1',
          requestId: `${instanceId}:audio:1`,
          elementToken: 'flama-audio-1',
        },
      },
    }))
    await Promise.resolve()

    const sharedAudio = document.querySelector('body > audio[aria-hidden="true"]')
    expect(sharedAudio?.getAttribute('src')).toBe(
      'https://api.flama.vn/media/proxy/derived-audio-1',
    )
    controller.destroy()
  })

  it('normalizes full backend media URLs to proxy refs regardless of origin', () => {
    const source = readFileSync(
      resolve(process.cwd(), '../static/js/card_renderer_host.js'),
      'utf8',
    )
    window.eval(source)

    const iframe = document.createElement('iframe')
    document.body.appendChild(iframe)
    const controller = window.FlamaCardRendererHost!.createRendererFrameController(
      iframe,
      { mediaBaseUrl: 'https://api.flama.vn/' },
    )
    controller.render({
      html: '<audio src="https://api.flama.vn/media/proxy/audio-remote-1"></audio>',
    })

    expect(iframe.srcdoc).toContain('https://api.flama.vn/media/proxy/audio-remote-1')
    controller.destroy()
  })

  describe('template script autonomy and inert attribute preservation', () => {
    function createSandbox(html: string) {
      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)
      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)
      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({ html })
      const sandbox = new JSDOM(iframe.srcdoc, { runScripts: 'dangerously' })
      const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
      return { controller, iframe, sandbox, instanceId }
    }

    it('does NOT mutate content or split $ automatically when no user script is present', async () => {
      const { controller, sandbox } = createSandbox(
        '<div auto-split>A$B$C</div>',
      )
      await new Promise((resolve) => setTimeout(resolve, 50))

      const root = sandbox.window.document.getElementById('flama-card-root')
      const target = root?.querySelector('[auto-split]')
      expect(target?.innerHTML).toBe('A$B$C')
      expect(target?.querySelectorAll('br').length).toBe(0)
      controller.destroy()
    })

    it('preserves auto-split and arbitrary inert custom attributes in sandbox iframe srcdoc', async () => {
      const { controller, iframe } = createSandbox(
        '<div auto-split data-auto-split my-marker="xyz" foo="bar">A$B</div>',
      )
      expect(iframe.srcdoc).toContain('auto-split')
      expect(iframe.srcdoc).toContain('data-auto-split')
      expect(iframe.srcdoc).toContain('my-marker="xyz"')
      expect(iframe.srcdoc).toContain('foo="bar"')
      controller.destroy()
    })

    it('allows user script to execute in sandbox and own template presentation logic', async () => {
      const { controller, sandbox } = createSandbox(`
        <div auto-split>lại $ nữa $ tiếp tục</div>
        <script>
          document.querySelectorAll('[auto-split]').forEach(function(el) {
            var raw = el.innerHTML;
            if (raw.indexOf('$') === -1) return;
            el.innerHTML = raw.split('$').map(function(s) {
              return '<div>' + s.trim() + '</div>';
            }).join('');
          });
        </script>
      `)
      await new Promise((resolve) => setTimeout(resolve, 50))

      const root = sandbox.window.document.getElementById('flama-card-root')
      const target = root?.querySelector('[auto-split]')
      expect(target?.innerHTML).toBe('<div>lại</div><div>nữa</div><div>tiếp tục</div>')
      expect(target?.querySelectorAll('div').length).toBe(3)
      controller.destroy()
    })
  })
})

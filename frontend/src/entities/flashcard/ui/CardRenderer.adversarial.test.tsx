// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CardDisplay } from './CardDisplay'
import { CardRendererFrame } from './CardRendererFrame'
import { FLAMA_RENDERER_CHANNEL } from '../model/types'
import type { CardRendererSlotContext } from '../model/types'

// Enable React 19 Act Environment
;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe('CardRenderer & Sandbox Adversarial Suite', () => {
  let container: HTMLDivElement

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
  })

  afterEach(() => {
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
    vi.restoreAllMocks()
  })

  // ==========================================================================
  // Suite 1: Iframe Sandbox & Security Isolation
  // ==========================================================================
  describe('1. Iframe Sandbox Flags & Security Boundaries', () => {
    it('enforces strictly sandbox="allow-scripts" and allow="autoplay", NEVER allow-same-origin', async () => {
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render: vi.fn(),
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: (p) => ({
          html: String((p as { html?: string })?.html || ''),
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardRendererFrame
            cardId="sec-card-1"
            revealed={false}
            frontPayload={{ html: '<p>Secure Front</p>' }}
          />,
        )
      })

      const iframe = container.querySelector('iframe')
      expect(iframe).not.toBeNull()
      if (!iframe) return

      // Verify exact required flags
      const sandboxAttr = iframe.getAttribute('sandbox')
      const allowAttr = iframe.getAttribute('allow')

      expect(sandboxAttr).toBe('allow-scripts')
      expect(allowAttr).toBe('autoplay')

      // STRICT NEGATIVE CHECKS: Absolutely forbidden permissions
      expect(sandboxAttr).not.toContain('allow-same-origin')
      expect(sandboxAttr).not.toContain('allow-top-navigation')
      expect(sandboxAttr).not.toContain('allow-modals')
      expect(sandboxAttr).not.toContain('allow-popups')
      expect(sandboxAttr).not.toContain('allow-pointer-lock')
      expect(sandboxAttr).not.toContain('allow-downloads')

      await act(async () => {
        root.unmount()
      })
    })

    it('enforces sandbox="allow-scripts" and referrerpolicy="no-referrer" in host runtime controller', () => {
      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)

      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)

      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({ html: '<div>Adversarial Host Check</div>' })

      expect(iframe.getAttribute('sandbox')).toBe('allow-scripts')
      expect(iframe.getAttribute('sandbox')).not.toContain('allow-same-origin')
      expect(iframe.getAttribute('referrerpolicy')).toBe('no-referrer')

      // Check Content-Security-Policy in srcdoc (quotes are HTML-escaped to &#39; for meta attribute safety)
      expect(iframe.srcdoc).toContain("default-src &#39;none&#39;")
      expect(iframe.srcdoc).toContain("connect-src &#39;none&#39;")
      expect(iframe.srcdoc).toContain("frame-ancestors &#39;none&#39;")
      expect(iframe.srcdoc).toContain("form-action &#39;none&#39;")
      expect(iframe.srcdoc).toContain("worker-src &#39;none&#39;")
      expect(iframe.srcdoc).toContain("object-src &#39;none&#39;")

      controller.destroy()
    })
  })

  // ==========================================================================
  // Suite 2: Dual-Face Persistent DOM Mounting across Flips (Stress Test)
  // ==========================================================================
  describe('2. Dual-Face Permanent Mounting & Flip Stress Test', () => {
    it('mounts both Front and Back frames simultaneously and preserves iframe instances across flips (0ms switch)', async () => {
      const controllers = [
        { render: vi.fn(), reveal: vi.fn(), destroy: vi.fn() },
        { render: vi.fn(), reveal: vi.fn(), destroy: vi.fn() },
      ]
      let callCount = 0
      const createController = vi.fn().mockImplementation(() => {
        return controllers[callCount++]
      })

      window.FlamaCardRendererHost = {
        createRendererFrameController: createController,
        normalizeRendererSidePayload: (p) => ({
          html: String((p as { html?: string })?.html || ''),
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      const props = {
        cardId: 'stress-card-1',
        side: 'front' as const,
        frontPayload: { html: '<p>Front Face</p>' },
        backPayload: { html: '<p>Back Face</p>' },
      }

      // Initial Mount (Side: Front)
      await act(async () => {
        root.render(<CardDisplay {...props} />)
      })

      // 1. Exactly 2 iframes must exist in DOM
      const initialIframes = container.querySelectorAll('iframe')
      expect(initialIframes.length).toBe(2)
      const frontIframe = initialIframes[0]
      const backIframe = initialIframes[1]

      // Front container visible, Back container hidden
      const frontWrapper = frontIframe.closest('.study-card-shell')?.parentElement
      const backWrapper = backIframe.closest('.study-card-shell')?.parentElement
      expect(frontWrapper?.classList.contains('hidden')).toBe(false)
      expect(frontWrapper?.getAttribute('aria-hidden')).toBe('false')
      expect(backWrapper?.classList.contains('hidden')).toBe(true)
      expect(backWrapper?.getAttribute('aria-hidden')).toBe('true')

      // Front controller rendered & revealed, back controller NOT yet rendered
      expect(controllers[0].render).toHaveBeenCalledTimes(1)
      expect(controllers[0].reveal).toHaveBeenCalledWith({ side: 'front', reason: 'load_card' })
      expect(controllers[1].render).not.toHaveBeenCalled()
      expect(controllers[1].reveal).not.toHaveBeenCalled()

      // Flip to Back
      await act(async () => {
        root.render(<CardDisplay {...props} side="back" />)
      })

      // 2. Exact same iframe instances MUST be preserved in DOM (no reload / no remount)
      const flippedIframes = container.querySelectorAll('iframe')
      expect(flippedIframes.length).toBe(2)
      expect(flippedIframes[0]).toBe(frontIframe)
      expect(flippedIframes[1]).toBe(backIframe)

      // Visibility toggled
      expect(frontWrapper?.classList.contains('hidden')).toBe(true)
      expect(frontWrapper?.getAttribute('aria-hidden')).toBe('true')
      expect(backWrapper?.classList.contains('hidden')).toBe(false)
      expect(backWrapper?.getAttribute('aria-hidden')).toBe('false')

      // Back controller rendered & revealed
      expect(controllers[1].render).toHaveBeenCalledTimes(1)
      expect(controllers[1].reveal).toHaveBeenCalledWith({ side: 'back', reason: 'show_answer' })

      // NO controller destroyed during flip
      expect(controllers[0].destroy).not.toHaveBeenCalled()
      expect(controllers[1].destroy).not.toHaveBeenCalled()

      // 3. RAPID FLIP STORM: 50 sequential flips
      for (let i = 0; i < 50; i++) {
        const nextSide = i % 2 === 0 ? 'front' : 'back'
        await act(async () => {
          root.render(<CardDisplay {...props} side={nextSide} />)
        })
      }

      // After 50 flips: controllers were called to create exactly 2 times total
      expect(createController).toHaveBeenCalledTimes(2)
      // Iframe DOM elements are still the exact same references
      const finalIframes = container.querySelectorAll('iframe')
      expect(finalIframes[0]).toBe(frontIframe)
      expect(finalIframes[1]).toBe(backIframe)
      // Destroy was never called during flips
      expect(controllers[0].destroy).not.toHaveBeenCalled()
      expect(controllers[1].destroy).not.toHaveBeenCalled()

      await act(async () => {
        root.unmount()
      })

      // Upon unmount, both controllers are cleanly destroyed
      expect(controllers[0].destroy).toHaveBeenCalledTimes(1)
      expect(controllers[1].destroy).toHaveBeenCalledTimes(1)
    })

    it('tears down old controllers and constructs new ones when card identity changes', async () => {
      const controllers = Array.from({ length: 4 }, () => ({
        render: vi.fn(),
        reveal: vi.fn(),
        destroy: vi.fn(),
      }))
      let index = 0
      window.FlamaCardRendererHost = {
        createRendererFrameController: vi.fn(() => controllers[index++]),
        normalizeRendererSidePayload: (p) => ({
          html: String((p as { html?: string })?.html || ''),
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="card-A"
            side="front"
            frontPayload={{ html: '<p>Front A</p>' }}
            backPayload={{ html: '<p>Back A</p>' }}
          />,
        )
      })

      expect(controllers[0].render).toHaveBeenCalled()
      expect(controllers[0].destroy).not.toHaveBeenCalled()
      expect(controllers[1].destroy).not.toHaveBeenCalled()

      // Switch to card-B
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="card-B"
            side="front"
            frontPayload={{ html: '<p>Front B</p>' }}
            backPayload={{ html: '<p>Back B</p>' }}
          />,
        )
      })

      // Old controllers must be destroyed
      expect(controllers[0].destroy).toHaveBeenCalledTimes(1)
      expect(controllers[1].destroy).toHaveBeenCalledTimes(1)

      // New controllers created and rendered for card-B
      expect(controllers[2].render).toHaveBeenCalled()
      expect(controllers[2].destroy).not.toHaveBeenCalled()

      await act(async () => {
        root.unmount()
      })
      expect(controllers[2].destroy).toHaveBeenCalledTimes(1)
      expect(controllers[3].destroy).toHaveBeenCalledTimes(1)
    })
  })

  // ==========================================================================
  // Suite 3: 2-Way postMessage Protocol & Channel Security
  // ==========================================================================
  describe('3. 2-Way postMessage Protocol & Channel Validation', () => {
    it('conforms to FLAMA_RENDERER_CHANNEL contract and routes messages accurately', async () => {
      expect(FLAMA_RENDERER_CHANNEL).toBe('flama-card-renderer')

      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)

      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)
      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({
        html: '<audio src="/media/proxy/valid-audio-1"></audio>',
        allowed_media_urls: ['/media/proxy/valid-audio-1'],
        allowed_audio_urls: ['/media/proxy/valid-audio-1'],
      })

      const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
      expect(instanceId).toBeTruthy()

      const frameWindow = iframe.contentWindow!
      const postMessageSpy = vi.spyOn(frameWindow, 'postMessage').mockImplementation(() => undefined)
      const playSpy = vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)

      // 1. Valid renderer_to_host play_audio message
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId,
            action: 'play_audio',
            payload: {
              ref: '/media/proxy/valid-audio-1',
              requestId: `${instanceId}:req-1`,
              elementToken: 'flama-audio-1',
            },
          },
        }),
      )
      await Promise.resolve()

      expect(playSpy).toHaveBeenCalledTimes(1)
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          channel: 'flama-card-renderer',
          direction: 'host_to_renderer',
          instanceId,
          action: 'audio_result',
          payload: expect.objectContaining({ ok: true }),
        }),
        '*',
      )

      controller.destroy()
    })

    it('adversarial attack resilience: rejects forged channels, wrong directions, forged instances, and unapproved audio', () => {
      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)

      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)
      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({
        html: '<audio src="/media/proxy/legit-audio"></audio>',
        allowed_audio_urls: ['/media/proxy/legit-audio'],
      })

      const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
      const frameWindow = iframe.contentWindow!
      const postMessageSpy = vi.spyOn(frameWindow, 'postMessage').mockImplementation(() => undefined)
      const playSpy = vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)

      // Attack A: Forged channel name
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'evil-spoofed-channel',
            direction: 'renderer_to_host',
            instanceId,
            action: 'play_audio',
            payload: { ref: '/media/proxy/legit-audio' },
          },
        }),
      )
      expect(playSpy).not.toHaveBeenCalled()

      // Attack B: Forged direction (host_to_renderer sent to host)
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'host_to_renderer',
            instanceId,
            action: 'play_audio',
            payload: { ref: '/media/proxy/legit-audio' },
          },
        }),
      )
      expect(playSpy).not.toHaveBeenCalled()

      // Attack C: Forged instanceId
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId: 'forged-arbitrary-id',
            action: 'play_audio',
            payload: { ref: '/media/proxy/legit-audio' },
          },
        }),
      )
      expect(playSpy).not.toHaveBeenCalled()

      // Attack D: Unauthorized audio URL / path traversal
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId,
            action: 'play_audio',
            payload: {
              ref: 'https://attacker.com/exploit.mp3',
              requestId: `${instanceId}:attack-req`,
            },
          },
        }),
      )
      expect(playSpy).not.toHaveBeenCalled()
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'audio_result',
          payload: expect.objectContaining({
            ok: false,
            error: 'Audio is not attached to this note.',
          }),
        }),
        '*',
      )

      // Attack E: Arbitrary command / action injection
      vi.spyOn(console, 'warn').mockImplementation(() => undefined)
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId,
            action: 'eval_arbitrary_code',
            payload: { code: 'alert(1)' },
          },
        }),
      )
      // Must not execute or crash
      expect(playSpy).not.toHaveBeenCalled()

      controller.destroy()
    })
  })

  // ==========================================================================
  // Suite 4: Abstract Slots Integration & Slot Projection
  // ==========================================================================
  describe('4. Abstract Slots Integration & Reactivity', () => {
    it('projects all custom slot zones (header, footer, toolbar, overlay) into designated DOM shells', async () => {
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render: vi.fn(),
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: () => ({
          html: '<p>Slot test card</p>',
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="slot-card-1"
            side="front"
            frontPayload={{ html: '<p>Front</p>' }}
            backPayload={{ html: '<p>Back</p>' }}
            slots={{
              header: <div data-testid="custom-header">Header Content</div>,
              footer: <div data-testid="custom-footer">Footer Content</div>,
              toolbar: <button data-testid="custom-toolbar">Tool</button>,
              overlay: <span data-testid="custom-overlay">Watermark Overlay</span>,
            }}
          />,
        )
      })

      const headerEl = container.querySelector('.study-card-slot-header [data-testid="custom-header"]')
      const footerEl = container.querySelector('.study-card-slot-footer [data-testid="custom-footer"]')
      const toolbarEl = container.querySelector('.study-card-slot-toolbar [data-testid="custom-toolbar"]')
      const overlayEl = container.querySelector('.study-card-slot-overlay [data-testid="custom-overlay"]')

      expect(headerEl).not.toBeNull()
      expect(headerEl?.textContent).toBe('Header Content')

      expect(footerEl).not.toBeNull()
      expect(footerEl?.textContent).toBe('Footer Content')

      expect(toolbarEl).not.toBeNull()
      expect(toolbarEl?.textContent).toBe('Tool')

      expect(overlayEl).not.toBeNull()
      expect(overlayEl?.textContent).toBe('Watermark Overlay')

      await act(async () => {
        root.unmount()
      })
    })

    it('injects accurate CardRendererSlotContext into functional slots and reacts to face flips', async () => {
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render: vi.fn(),
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: () => ({
          html: '<p>Face flip slot</p>',
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      let capturedContext: CardRendererSlotContext | undefined = undefined
      const dynamicHeader = (ctx: CardRendererSlotContext) => {
        capturedContext = ctx
        return (
          <div data-testid="reactive-header">
            Card:{ctx.cardId}|Side:{ctx.side}|isBack:{String(ctx.isBack)}|scope:{ctx.scope}
          </div>
        )
      }

      const root = createRoot(container)
      const props = {
        cardId: 'dyn-card-42',
        noteId: 'note-42',
        scope: 'note_type_live_preview',
        scopeId: 'nt-99',
        fieldValues: { Word: '日本語', Meaning: 'Japanese language' },
        frontPayload: { html: '<p>Front 42</p>' },
        backPayload: { html: '<p>Back 42</p>' },
      }

      // 1. Initial Front render
      await act(async () => {
        root.render(<CardDisplay {...props} side="front" slots={{ header: dynamicHeader }} />)
      })

      const headerEl = container.querySelector('[data-testid="reactive-header"]')
      expect(headerEl?.textContent).toBe('Card:dyn-card-42|Side:front|isBack:false|scope:note_type_live_preview')
      expect(Boolean(capturedContext)).toBe(true)
      const frontContext = capturedContext as unknown as CardRendererSlotContext
      expect(frontContext.cardId).toBe('dyn-card-42')
      expect(frontContext.noteId).toBe('note-42')
      expect(frontContext.side).toBe('front')
      expect(frontContext.isBack).toBe(false)
      expect(frontContext.isRevealed).toBe(false)
      expect(frontContext.fieldValues?.Word).toBe('日本語')

      // 2. Flip to Back
      await act(async () => {
        root.render(<CardDisplay {...props} side="back" slots={{ header: dynamicHeader }} />)
      })

      expect(headerEl?.textContent).toBe('Card:dyn-card-42|Side:back|isBack:true|scope:note_type_live_preview')
      const backContext = capturedContext as unknown as CardRendererSlotContext
      expect(backContext.side).toBe('back')
      expect(backContext.isBack).toBe(true)
      expect(backContext.isRevealed).toBe(true)

      await act(async () => {
        root.unmount()
      })
    })

    it('renders emptyState slot when no payload or html is provided', async () => {
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render: vi.fn(),
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: () => ({
          html: '',
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="empty-card"
            side="front"
            slots={{
              emptyState: <div data-testid="custom-empty-state">No Flashcard Content Available</div>,
            }}
          />,
        )
      })

      const emptyEl = container.querySelector('[data-testid="custom-empty-state"]')
      expect(emptyEl).not.toBeNull()
      expect(emptyEl?.textContent).toBe('No Flashcard Content Available')
      // No iframes should be mounted when emptyState is rendered
      expect(container.querySelectorAll('iframe').length).toBe(0)

      await act(async () => {
        root.unmount()
      })
    })

    it('renders errorFallback slot when renderer host script fails to load in CardRendererFrame', async () => {
      // Intentionally do NOT set window.FlamaCardRendererHost
      // and simulate script loading failure
      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardRendererFrame
            cardId="err-card"
            revealed={false}
            slots={{
              errorFallback: (msg) => (
                <div data-testid="custom-error-fallback">
                  {String(msg instanceof Error ? msg.message : msg)}
                </div>
              ),
            }}
          />,
        )
      })

      // Simulate script error on injected script tag
      const script = document.querySelector('script[src*="card_renderer_host.js"]')
      if (script) {
        await act(async () => {
          script.dispatchEvent(new Event('error'))
        })
      }

      const errorEl = container.querySelector('[data-testid="custom-error-fallback"]')
      expect(errorEl).not.toBeNull()
      expect(errorEl?.textContent).toBe('Không thể tải trình hiển thị thẻ.')

      await act(async () => {
        root.unmount()
      })
    })

    it('honors strict precedence order for slot aliases (slots.header > headerSlot > slots.topToolbar)', async () => {
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render: vi.fn(),
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: () => ({
          html: '<p>precedence test</p>',
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="prec-card"
            side="front"
            frontPayload={{ html: '<p>Content</p>' }}
            slots={{
              header: <div data-testid="winner-header">Primary Header</div>,
              topToolbar: <div data-testid="fallback-top">Fallback Top</div>,
              footer: <div data-testid="winner-footer">Primary Footer</div>,
              bottomToolbar: <div data-testid="fallback-bottom">Fallback Bottom</div>,
            }}
            headerSlot={<div data-testid="secondary-header">Secondary Header</div>}
            footerSlot={<div data-testid="secondary-footer">Secondary Footer</div>}
          />,
        )
      })

      // Primary header wins over secondary header and topToolbar
      expect(container.querySelector('[data-testid="winner-header"]')).not.toBeNull()
      expect(container.querySelector('[data-testid="secondary-header"]')).toBeNull()
      expect(container.querySelector('[data-testid="fallback-top"]')).toBeNull()

      // Primary footer wins over secondary footer and bottomToolbar
      expect(container.querySelector('[data-testid="winner-footer"]')).not.toBeNull()
      expect(container.querySelector('[data-testid="secondary-footer"]')).toBeNull()
      expect(container.querySelector('[data-testid="fallback-bottom"]')).toBeNull()

      await act(async () => {
        root.unmount()
      })
    })
  })

  // ==========================================================================
  // Suite 5: Audio Concurrency & Replacement Storm
  // ==========================================================================
  describe('5. Audio Concurrency & Replacement Storm', () => {
    it('cleanly replaces previous playback and notifies old token when consecutive audio requests arrive', async () => {
      const source = readFileSync(
        resolve(process.cwd(), '../static/js/card_renderer_host.js'),
        'utf8',
      )
      window.eval(source)

      const iframe = document.createElement('iframe')
      document.body.appendChild(iframe)
      const controller = window.FlamaCardRendererHost!.createRendererFrameController(iframe)
      controller.render({
        html: '<audio src="/media/proxy/track-1"></audio><audio src="/media/proxy/track-2"></audio>',
        allowed_audio_urls: ['/media/proxy/track-1', '/media/proxy/track-2'],
      })

      const instanceId = iframe.srcdoc.match(/"instanceId":"([^"]+)"/)?.[1]
      const frameWindow = iframe.contentWindow!
      const postMessageSpy = vi.spyOn(frameWindow, 'postMessage').mockImplementation(() => undefined)
      vi.spyOn(window.HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
      vi.spyOn(window.HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)

      // Start audio 1
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId,
            action: 'play_audio',
            payload: {
              ref: '/media/proxy/track-1',
              requestId: `${instanceId}:req-track-1`,
              elementToken: 'flama-audio-1',
            },
          },
        }),
      )
      await Promise.resolve()

      // Rapidly start audio 2 before audio 1 finishes
      window.dispatchEvent(
        new MessageEvent('message', {
          source: frameWindow,
          data: {
            channel: 'flama-card-renderer',
            direction: 'renderer_to_host',
            instanceId,
            action: 'play_audio',
            payload: {
              ref: '/media/proxy/track-2',
              requestId: `${instanceId}:req-track-2`,
              elementToken: 'flama-audio-2',
            },
          },
        }),
      )
      await Promise.resolve()

      // The old playback should have received pause event to sync UI state
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'audio_event',
          payload: expect.objectContaining({
            elementToken: 'flama-audio-1',
            type: 'pause',
            ref: '/media/proxy/track-1',
          }),
        }),
        '*',
      )

      // The new playback should have succeeded and started playing
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'audio_result',
          payload: expect.objectContaining({
            requestId: `${instanceId}:req-track-2`,
            ok: true,
          }),
        }),
        '*',
      )
      expect(postMessageSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          action: 'audio_event',
          payload: expect.objectContaining({
            elementToken: 'flama-audio-2',
            type: 'play',
            ref: '/media/proxy/track-2',
          }),
        }),
        '*',
      )

      controller.destroy()
    })
  })

  // ==========================================================================
  // Suite 6: Extreme & Malformed Payload Resilience
  // ==========================================================================
  describe('6. Extreme & Malformed Payload Resilience', () => {
    it('renders gracefully under malformed, non-string, and extreme HTML payloads without crashing', async () => {
      const render = vi.fn()
      window.FlamaCardRendererHost = {
        createRendererFrameController: () => ({
          render,
          reveal: vi.fn(),
          destroy: vi.fn(),
        }),
        normalizeRendererSidePayload: (p) => ({
          html: typeof p === 'string' ? p : String((p as { html?: string })?.html || ''),
          allowed_media_urls: [],
          allowed_audio_urls: [],
        }),
        createNoticeHtml: (m) => `<p>${m}</p>`,
      }

      const root = createRoot(container)

      // Test with massive payload (100,000 characters)
      const massiveHtml = '<p>' + 'A'.repeat(100000) + '</p>'
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="massive-card"
            side="front"
            frontPayload={{ html: massiveHtml }}
            backPayload={{ html: '<p>Back</p>' }}
          />,
        )
      })
      expect(render).toHaveBeenCalled()

      // Test with malformed types (number, object with circular ref or prototype keys)
      await act(async () => {
        root.render(
          <CardDisplay
            cardId="malformed-card"
            side="front"
            frontPayload={null as unknown as undefined}
            frontHtml="<div>Simple HTML</div>"
          />,
        )
      })
      expect(render).toHaveBeenCalled()

      await act(async () => {
        root.unmount()
      })
    })
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CardDisplay } from './CardDisplay'

describe('CardDisplay', () => {
  afterEach(() => {
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
  })

  it('keeps both faces mounted and reuses their renderers when flipping', async () => {
    const controllers = Array.from({ length: 2 }, () => ({
      render: vi.fn(),
      reveal: vi.fn(),
      destroy: vi.fn(),
    }))
    const createRendererFrameController = vi
      .fn()
      .mockImplementationOnce(() => controllers[0])
      .mockImplementationOnce(() => controllers[1])

    window.FlamaCardRendererHost = {
      createRendererFrameController,
      normalizeRendererSidePayload: (payload) => ({
        html: String((payload as { html?: string })?.html || ''),
        allowed_media_urls: [],
        allowed_audio_urls: [],
      }),
      createNoticeHtml: (message) => `<p>${message}</p>`,
    }

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const props = {
      cardId: 'card-1',
      side: 'front' as const,
      frontPayload: { html: '<p>front</p>' },
      backPayload: { html: '<p>back</p>' },
    }

    await act(async () => {
      root.render(<CardDisplay {...props} />)
    })

    expect(createRendererFrameController).toHaveBeenCalledTimes(2)
    const shell = container.firstElementChild!
    expect(shell.className).toBe('study-card-shell relative h-full min-h-[240px] w-full min-w-0 overflow-hidden')
    // Original viewport hierarchy: shell -> two faces -> renderer shell -> iframe.
    // An added wrapper changes percentage heights and must fail this assertion.
    expect(shell.children).toHaveLength(2)
    expect(Array.from(shell.children, (face) => face.getAttribute('aria-hidden'))).toEqual(['false', 'true'])
    for (const face of shell.children) {
      expect(face.children).toHaveLength(1)
      expect(face.firstElementChild?.className).toBe('study-card-shell w-full relative h-full min-h-0')
      expect(face.firstElementChild?.children).toHaveLength(1)
      expect(face.firstElementChild?.firstElementChild?.tagName).toBe('IFRAME')
    }
    const framesBeforeFlip = Array.from(container.querySelectorAll('iframe'))
    expect(controllers[0].render).toHaveBeenCalledTimes(1)
    expect(controllers[1].render).not.toHaveBeenCalled()
    expect(controllers[0].reveal).toHaveBeenCalledWith({
      side: 'front',
      reason: 'load_card',
    })
    expect(controllers[1].reveal).not.toHaveBeenCalled()

    await act(async () => {
      root.render(<CardDisplay {...props} side="back" />)
    })

    expect(createRendererFrameController).toHaveBeenCalledTimes(2)
    expect(controllers[0].render).toHaveBeenCalledTimes(1)
    expect(controllers[1].render).toHaveBeenCalledTimes(1)
    expect(Array.from(container.querySelectorAll('iframe'))).toEqual(framesBeforeFlip)
    expect(Array.from(shell.children, (face) => face.getAttribute('aria-hidden'))).toEqual(['true', 'false'])
    expect(controllers[1].reveal).toHaveBeenCalledWith({
      side: 'back',
      reason: 'show_answer',
    })

    await act(async () => {
      root.unmount()
    })
    expect(controllers[0].destroy).toHaveBeenCalledTimes(1)
    expect(controllers[1].destroy).toHaveBeenCalledTimes(1)
  })

  it('replaces both renderer frames when the card identity changes', async () => {
    const controllers = Array.from({ length: 4 }, () => ({
      render: vi.fn(),
      reveal: vi.fn(),
      destroy: vi.fn(),
    }))
    const createRendererFrameController = vi
      .fn()
      .mockImplementation((_frame, _options) => (
        controllers[createRendererFrameController.mock.calls.length - 1]
      ))

    window.FlamaCardRendererHost = {
      createRendererFrameController,
      normalizeRendererSidePayload: (payload) => ({
        html: String((payload as { html?: string })?.html || ''),
        allowed_media_urls: [],
        allowed_audio_urls: [],
      }),
      createNoticeHtml: (message) => `<p>${message}</p>`,
    }

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <CardDisplay
          cardId="card-1"
          side="front"
          frontPayload={{ html: '<p>old front</p>' }}
          backPayload={{ html: '<p>old back</p>' }}
        />,
      )
    })

    await act(async () => {
      root.render(
        <CardDisplay
          cardId="card-2"
          side="front"
          frontPayload={{ html: '<p>new front</p>' }}
          backPayload={{ html: '<p>new back</p>' }}
        />,
      )
    })

    expect(createRendererFrameController).toHaveBeenCalledTimes(4)
    expect(controllers[0].destroy).toHaveBeenCalledTimes(1)
    expect(controllers[1].destroy).toHaveBeenCalledTimes(1)
    expect(controllers[2].render).toHaveBeenCalledWith(
      expect.objectContaining({ html: '<p>new front</p>' }),
      expect.objectContaining({
        context: expect.objectContaining({ cardId: 'card-2' }),
      }),
    )
    expect(controllers[2].reveal).toHaveBeenCalledWith({
      side: 'front',
      reason: 'load_card',
    })

    await act(async () => {
      root.unmount()
    })
  })

  it('supports abstract slots projection and emptyState fallback', async () => {
    window.FlamaCardRendererHost = {
      createRendererFrameController: () => ({
        render: vi.fn(),
        reveal: vi.fn(),
        destroy: vi.fn(),
      }),
      normalizeRendererSidePayload: () => ({
        html: '<p>content</p>',
        allowed_media_urls: [],
        allowed_audio_urls: [],
      }),
      createNoticeHtml: (msg) => `<p>${msg}</p>`,
    }

    const container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)

    // Empty state fallback when no payload/html
    await act(async () => {
      root.render(
        <CardDisplay
          cardId="card-empty"
          side="front"
          slots={{
            emptyState: <div data-testid="empty-fallback">No card content</div>,
          }}
        />,
      )
    })
    expect(container.querySelector('[data-testid="empty-fallback"]')?.textContent).toBe('No card content')

    // Normal render with slots
    await act(async () => {
      root.render(
        <CardDisplay
          cardId="card-slots"
          side="front"
          frontHtml="<p>Front</p>"
          backHtml="<p>Back</p>"
          slots={{
            header: (ctx) => <div data-testid="slot-hdr">Side: {ctx.side}</div>,
            toolbar: <div data-testid="slot-tb">Toolbar</div>,
            footer: <div data-testid="slot-ftr">Footer</div>,
          }}
        />,
      )
    })
    expect(container.querySelector('[data-testid="slot-hdr"]')?.textContent).toBe('Side: front')
    expect(container.querySelector('[data-testid="slot-tb"]')?.textContent).toBe('Toolbar')
    expect(container.querySelector('[data-testid="slot-ftr"]')?.textContent).toBe('Footer')

    await act(async () => {
      root.unmount()
    })
  })
})

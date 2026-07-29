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
    expect(controllers[0].render).toHaveBeenCalledTimes(1)
    expect(controllers[1].render).toHaveBeenCalledTimes(1)
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
})

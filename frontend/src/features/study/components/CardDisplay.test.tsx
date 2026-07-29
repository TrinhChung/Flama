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
})

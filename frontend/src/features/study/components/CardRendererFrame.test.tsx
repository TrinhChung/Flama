// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CardRendererFrame } from './CardRendererFrame'

describe('CardRendererFrame', () => {
  afterEach(() => {
    document.body.replaceChildren()
    delete window.FlamaCardRendererHost
  })

  it('keeps one live-patch controller across visibility changes and cleans it up', async () => {
    const render = vi.fn()
    const reveal = vi.fn()
    const destroy = vi.fn()
    const createRendererFrameController = vi.fn(() => ({
      render,
      reveal,
      destroy,
    }))
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
      noteId: 'note-1',
      revealed: false,
      frontPayload: { html: '<p>front</p>' },
      active: false,
      enableLivePatch: true,
      fillHeight: true,
    }

    await act(async () => {
      root.render(<CardRendererFrame {...props} />)
    })

    expect(createRendererFrameController).toHaveBeenCalledTimes(1)
    expect(createRendererFrameController).toHaveBeenCalledWith(
      expect.any(HTMLIFrameElement),
      expect.objectContaining({
        autoHeight: false,
        enableLivePatch: true,
        fillHeight: true,
      }),
    )
    expect(render).toHaveBeenCalledTimes(1)
    expect(reveal).not.toHaveBeenCalled()

    await act(async () => {
      root.render(<CardRendererFrame {...props} active />)
    })

    expect(createRendererFrameController).toHaveBeenCalledTimes(1)
    expect(render).toHaveBeenCalledTimes(1)
    expect(reveal).toHaveBeenCalledWith({
      side: 'front',
      reason: 'load_card',
    })

    await act(async () => {
      root.unmount()
    })
    expect(destroy).toHaveBeenCalledTimes(1)
  })
})

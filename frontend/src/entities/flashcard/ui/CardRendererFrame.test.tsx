// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CardRendererFrame } from './CardRendererFrame'
import { CardDisplay } from './CardDisplay'

describe('CardRendererFrame', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
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
    expect(render).not.toHaveBeenCalled()
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

  it('renders abstract slots correctly', async () => {
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

    await act(async () => {
      root.render(
        <CardRendererFrame
          cardId="card-slot-test"
          revealed={false}
          slots={{
            header: <div data-testid="test-header">Header Slot</div>,
            toolbar: <div data-testid="test-toolbar">Toolbar Slot</div>,
            footer: <div data-testid="test-footer">Footer Slot</div>,
          }}
        />,
      )
    })

    expect(container.querySelector('[data-testid="test-header"]')?.textContent).toBe('Header Slot')
    expect(container.querySelector('[data-testid="test-toolbar"]')?.textContent).toBe('Toolbar Slot')
    expect(container.querySelector('[data-testid="test-footer"]')?.textContent).toBe('Footer Slot')

    await act(async () => {
      root.unmount()
    })
  })

  it('retains both face documents on flips and applies changes made while a face is inactive', async () => {
    const controllers: Array<{ render: ReturnType<typeof vi.fn>; reveal: ReturnType<typeof vi.fn>; destroy: ReturnType<typeof vi.fn> }> = []
    window.FlamaCardRendererHost = {
      createRendererFrameController: () => {
        const controller = { render: vi.fn(), reveal: vi.fn(), destroy: vi.fn() }
        controllers.push(controller)
        return controller
      },
      normalizeRendererSidePayload: (payload) => ({ html: (payload as { html: string }).html, allowed_media_urls: [], allowed_audio_urls: [] }),
      createNoticeHtml: (message) => message,
    }
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    const props = { cardId: 'interactive', frontPayload: { html: '<button>front</button>' }, backPayload: { html: '<p>back</p>' } }
    await act(async () => root.render(<CardDisplay {...props} side="front" />))
    const [front, back] = controllers
    expect(front!.render).toHaveBeenCalledTimes(1)
    expect(back!.render).not.toHaveBeenCalled()
    await act(async () => root.render(<CardDisplay {...props} side="back" />))
    await act(async () => root.render(<CardDisplay {...props} side="front" />))
    expect(controllers).toHaveLength(2)
    expect(front!.render).toHaveBeenCalledTimes(1)
    expect(back!.render).toHaveBeenCalledTimes(1)
    expect(front!.reveal).toHaveBeenCalledTimes(2)
    const updated = { ...props, frontPayload: { html: '<button>updated</button>' } }
    await act(async () => root.render(<CardDisplay {...updated} side="back" />))
    expect(front!.render).toHaveBeenCalledTimes(1)
    await act(async () => root.render(<CardDisplay {...updated} side="front" />))
    expect(front!.render).toHaveBeenCalledTimes(2)
    expect(front!.render).toHaveBeenLastCalledWith(expect.objectContaining({ html: '<button>updated</button>' }), expect.anything())
    await act(async () => root.render(<CardDisplay {...updated} side="front" mediaBaseUrl="https://api.flama.vn/" />))
    expect(front!.destroy).toHaveBeenCalledTimes(1)
    expect(controllers).toHaveLength(4)
    expect(controllers[2]!.render).toHaveBeenCalledTimes(1)
    await act(async () => root.unmount())
  })

  it('passes candidate identity and media origin, and updates callbacks without reloading the frame', async () => {
    const render = vi.fn()
    const createRendererFrameController = vi.fn((_iframe: HTMLIFrameElement, _options?: Record<string, unknown>) => ({ render, reveal: vi.fn(), destroy: vi.fn() }))
    window.FlamaCardRendererHost = {
      createRendererFrameController,
      normalizeRendererSidePayload: () => ({ html: '<p>front</p>', allowed_media_urls: [], allowed_audio_urls: [] }),
      createNoticeHtml: (message) => message,
    }
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    const first = vi.fn()
    const second = vi.fn()
    const ready = vi.fn()
    const props = { cardId: 'preview', candidateHash: 'sha256-candidate', frontHtml: 'front', revealed: false, mediaBaseUrl: 'https://api.flama.vn/' }
    await act(async () => root.render(<CardRendererFrame {...props} onDiagnostic={first} onReady={ready} />))
    expect(render).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ context: expect.objectContaining({ candidateHash: 'sha256-candidate' }) }))
    const options = createRendererFrameController.mock.calls[0]![1] as Record<string, unknown>
    expect(options.mediaBaseUrl).toBe('https://api.flama.vn/')
    await act(async () => root.render(<CardRendererFrame {...props} onDiagnostic={second} onReady={ready} />))
    const diagnostic = { code: 'SANDBOX_RUNTIME_ERROR', stage: 'runtime', message: 'failure', side: 'front', cardId: 'preview', candidateHash: 'sha256-candidate' }
    ;(options.onError as (value: unknown) => void)(diagnostic)
    ;(options.onReady as (value: unknown) => void)({ side: 'front', candidateHash: 'sha256-candidate' })
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledWith(diagnostic)
    expect(ready).toHaveBeenCalledTimes(1)
    expect(createRendererFrameController).toHaveBeenCalledTimes(1)
    await act(async () => root.unmount())
  })

  it('reports a renderer-host load failure with candidate context', async () => {
    const onDiagnostic = vi.fn()
    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)
    await act(async () => root.render(<CardRendererFrame cardId="preview" candidateHash="candidate" revealed={false} frontHtml="front" onDiagnostic={onDiagnostic} />))
    const script = document.querySelector<HTMLScriptElement>('script[src*="card_renderer_host.js"]')!
    await act(async () => script.dispatchEvent(new Event('error')))
    expect(onDiagnostic).toHaveBeenCalledWith(expect.objectContaining({ code: 'RENDERER_HOST_LOAD_FAILED', cardId: 'preview', candidateHash: 'candidate', side: 'front' }))
    expect(container.textContent).toContain('Không thể tải trình hiển thị thẻ.')
    await act(async () => root.unmount())
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MediaFieldPreview, resolveDisplayUrl } from './MediaFieldPreview'

describe('MediaFieldPreview', () => {
  let container: HTMLDivElement | null = null

  afterEach(() => {
    container?.remove()
    container = null
    document.body.replaceChildren()
  })

  async function render(
    value: string,
    fieldType: 'image' | 'audio' | 'diagram' = 'image',
    onChange = vi.fn(),
  ) {
    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    await act(async () => {
      root.render(
        <MediaFieldPreview
          fieldName={fieldType === 'audio' ? 'Audio' : 'Illustration'}
          fieldType={fieldType}
          value={value}
          onChange={onChange}
        />,
      )
    })
    return { container, onChange, root }
  }

  it('renders image preview by default and hides raw URL textarea in preview mode', async () => {
    const { container: view } = await render('https://example.com/cat.png')
    expect(view.querySelector('img')?.src).toBe('https://example.com/cat.png')
    expect(view.querySelector('textarea')).toBeNull()
  })

  it('renders every newline-separated image URL in preview mode', async () => {
    const { container: view } = await render('https://example.com/1.png\nhttps://example.com/2.png')
    expect(view.querySelectorAll('img')).toHaveLength(2)
    expect(view.querySelector('textarea')).toBeNull()
  })

  it('switches between preview, url, and code modes', async () => {
    const { container: view } = await render('https://example.com/sound.mp3', 'audio')

    // Mode 1: Preview (default) - audio player visible, textarea hidden
    expect(view.querySelector('audio')).not.toBeNull()
    expect(view.querySelector('textarea')).toBeNull()
    expect(view.querySelector('pre')).toBeNull()

    // Switch to Mode 2: URL
    const urlButton = view.querySelector('button[title="Đường dẫn URL gốc"]') as HTMLButtonElement
    await act(async () => urlButton.click())

    expect(view.querySelector('textarea')).not.toBeNull()
    expect((view.querySelector('textarea') as HTMLTextAreaElement).value).toBe('https://example.com/sound.mp3')
    expect(view.querySelector('audio')).toBeNull()

    // Switch to Mode 3: Code (Read-only)
    const codeButton = view.querySelector('button[title="Mã HTML (chỉ xem)"]') as HTMLButtonElement
    await act(async () => codeButton.click())

    expect(view.querySelector('pre')?.textContent).toContain(
      '<audio controls src="https://example.com/sound.mp3"></audio>',
    )
    expect(view.querySelector('textarea')).toBeNull()
    expect(view.querySelector('button[title="Sao chép mã HTML"]')).not.toBeNull()

    // Switch back to Preview
    const previewButton = view.querySelector('button[title^="Xem trước"]') as HTMLButtonElement
    await act(async () => previewButton.click())

    expect(view.querySelector('audio')).not.toBeNull()
    expect(view.querySelector('textarea')).toBeNull()
  })

  it('recognizes staged and asset URLs as canonical preview sources', async () => {
    const { container: view } = await render(
      '/media/staged/stg_1234567890abcdef\n/media/asset/asset_12345678',
      'image',
    )
    const images = view.querySelectorAll('img')
    expect(images).toHaveLength(2)
    expect(images[0].getAttribute('src')).toBe('/media/staged/stg_1234567890abcdef')
    expect(images[1].getAttribute('src')).toBe('/media/asset/asset_12345678')
  })

  it('shows invalid URL warning when switched to URL mode', async () => {
    const { container: view } = await render('legacy.mp3', 'audio')
    expect(view.querySelector('audio')).toBeNull()

    const urlButton = view.querySelector('button[title="Đường dẫn URL gốc"]') as HTMLButtonElement
    await act(async () => urlButton.click())

    expect(view.querySelector('textarea')).not.toBeNull()
    expect(view.textContent).toContain('1 dòng không phải URL media hợp lệ')
  })

  it('renders an empty placeholder with paste hint in preview mode', async () => {
    const { container: view } = await render('', 'diagram')
    expect(view.textContent).toContain('Chưa có ảnh')
    expect(view.textContent).toContain('Ctrl+V')
    expect(view.querySelector('textarea')).toBeNull()
  })

  it('handles paste of URL directly onto the preview container', async () => {
    const onChange = vi.fn()
    const { container: view } = await render('', 'image', onChange)

    const previewContainer = view.querySelector('[tabindex="0"]') as HTMLDivElement
    expect(previewContainer).not.toBeNull()

    const pasteEvent = new Event('paste', { bubbles: true, cancelable: true }) as any
    pasteEvent.clipboardData = {
      items: [],
      files: [],
      getData: (format: string) => (format === 'text' ? 'https://example.com/pasted.png' : ''),
    }

    await act(async () => {
      previewContainer.dispatchEvent(pasteEvent)
    })

    expect(onChange).toHaveBeenCalledWith('https://example.com/pasted.png')
  })

  it('unwraps [sound:...] syntax for audio and supports custom resolveUrl', async () => {
    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    const resolveUrl = vi.fn((raw: string) => {
      if (raw === 'custom_sound.mp3') return 'https://example.com/custom_sound.mp3'
      return undefined
    })

    await act(async () => {
      root.render(
        <MediaFieldPreview
          fieldName="Audio"
          fieldType="audio"
          value="[sound:custom_sound.mp3]"
          onChange={vi.fn()}
          resolveUrl={resolveUrl}
        />,
      )
    })

    expect(resolveUrl).toHaveBeenCalledWith('custom_sound.mp3')
    const audio = container.querySelector('audio')
    expect(audio).not.toBeNull()
    expect(audio?.src).toBe('https://example.com/custom_sound.mp3')
  })

  it('stages original pasted images on the media worker without changing the saved note', async () => {
    const media = await import('@/entities/flashcard/api/media')
    const stageSpy = vi.spyOn(media, 'stageNoteMedia').mockResolvedValue({
      stage_id: `stg_${'a'.repeat(32)}`, asset_id: 'b'.repeat(64), sha256: 'b'.repeat(64),
      url: 'https://media.example.test/media/staged/stg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
      size_bytes: 100, content_type: 'image/png',
    })
    const client = await import('@/shared/api/client')
    const requestSpy = vi.spyOn(client, 'apiRequest')
    requestSpy.mockClear()
    const onChange = vi.fn()
    const { container: view } = await render('', 'image', onChange)
    const previewContainer = view.querySelector('[tabindex="0"]') as HTMLDivElement
    const largeFile = new File([new ArrayBuffer(3 * 1024 * 1024)], 'huge.png', { type: 'image/png' })
    const pasteEvent = new Event('paste', { bubbles: true, cancelable: true }) as any
    pasteEvent.clipboardData = {
      items: [{ type: 'image/png', getAsFile: () => largeFile }],
      files: [largeFile], getData: () => '',
    }
    await act(async () => { previewContainer.dispatchEvent(pasteEvent) })
    expect(stageSpy).toHaveBeenCalledWith(largeFile, 'huge.png', {}, expect.any(AbortSignal))
    expect(onChange).toHaveBeenCalledWith('https://media.example.test/media/staged/stg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    expect(requestSpy).not.toHaveBeenCalled()
    stageSpy.mockRestore()
  })

  it('cancels the upload when its editor unmounts and ignores a late worker response', async () => {
    const media = await import('@/entities/flashcard/api/media')
    let finishUpload: (value: Awaited<ReturnType<typeof media.stageNoteMedia>>) => void
    const stageSpy = vi.spyOn(media, 'stageNoteMedia').mockImplementation(() => new Promise((resolve) => {
      finishUpload = resolve
    }))
    const { container: view, onChange, root } = await render('')
    const image = new File(['raw'], 'clipboard.png', { type: 'image/png' })
    const paste = new Event('paste', { bubbles: true, cancelable: true }) as any
    paste.clipboardData = { items: [{ type: image.type, getAsFile: () => image }], files: [image], getData: () => '' }
    await act(async () => { view.querySelector('[tabindex="0"]')!.dispatchEvent(paste) })
    const signal = stageSpy.mock.calls[0][3]!
    act(() => root.unmount())
    expect(signal.aborted).toBe(true)
    await act(async () => finishUpload!({
      stage_id: `stg_${'a'.repeat(32)}`, asset_id: 'b'.repeat(64), sha256: 'b'.repeat(64),
      url: 'https://media.example.test/media/staged/stg_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', size_bytes: 3, content_type: image.type,
    }))
    expect(onChange).not.toHaveBeenCalled()
    stageSpy.mockRestore()
  })

  it('refuses pasted image files when uploads are disabled but still accepts links', async () => {
    const { toast } = await import('sonner')
    const toastErrorSpy = vi.spyOn(toast, 'error')
    const client = await import('@/shared/api/client')
    const requestSpy = vi.spyOn(client, 'apiRequest')
    const onChange = vi.fn()

    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    await act(async () => {
      root.render(
        <MediaFieldPreview fieldName="Picture" fieldType="image" value="" onChange={onChange} uploadDisabled />,
      )
    })
    expect(container.textContent).toContain('Thẻ này không hỗ trợ tải ảnh lên')
    const previewContainer = container.querySelector('[tabindex="0"]') as HTMLDivElement

    const file = new File(['x'], 'cat.png', { type: 'image/png' })
    const imagePaste = new Event('paste', { bubbles: true, cancelable: true }) as any
    imagePaste.clipboardData = { items: [{ type: 'image/png', getAsFile: () => file }], files: [file], getData: () => '' }
    await act(async () => {
      previewContainer.dispatchEvent(imagePaste)
    })
    expect(toastErrorSpy).toHaveBeenCalledWith('Thẻ này không hỗ trợ tải ảnh lên. Hãy dán link ảnh.')
    expect(requestSpy).not.toHaveBeenCalled()
    expect(onChange).not.toHaveBeenCalled()

    const linkPaste = new Event('paste', { bubbles: true, cancelable: true }) as any
    linkPaste.clipboardData = { items: [], files: [], getData: (format: string) => (format === 'text' ? 'https://example.com/cat.png' : '') }
    await act(async () => {
      previewContainer.dispatchEvent(linkPaste)
    })
    expect(onChange).toHaveBeenCalledWith('https://example.com/cat.png')
    act(() => root.unmount())
  })

  it("uses the address Chrome's Copy image puts beside the picture when uploads are off", async () => {
    const { toast } = await import('sonner')
    const toastErrorSpy = vi.spyOn(toast, 'error')
    toastErrorSpy.mockClear()
    const client = await import('@/shared/api/client')
    const requestSpy = vi.spyOn(client, 'apiRequest')
    requestSpy.mockClear()
    const onChange = vi.fn()

    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    await act(async () => {
      root.render(
        <MediaFieldPreview fieldName="Picture" fieldType="image" value="" onChange={onChange} uploadDisabled />,
      )
    })
    const previewContainer = container.querySelector('[tabindex="0"]') as HTMLDivElement
    const file = new File(['x'], 'image.png', { type: 'image/png' })
    const chromeCopy = new Event('paste', { bubbles: true, cancelable: true }) as any
    chromeCopy.clipboardData = {
      items: [{ type: 'text/html', getAsFile: () => null }, { type: 'image/png', getAsFile: () => file }],
      files: [file],
      getData: (format: string) => (format === 'text/html'
        ? '<html><body><!--StartFragment--><img src="https://example.com/dog.jpg" alt="dog"/><!--EndFragment--></body></html>'
        : ''),
    }
    await act(async () => {
      previewContainer.dispatchEvent(chromeCopy)
    })
    expect(onChange).toHaveBeenCalledWith('https://example.com/dog.jpg')
    expect(toastErrorSpy).not.toHaveBeenCalledWith('Thẻ này không hỗ trợ tải ảnh lên. Hãy dán link ảnh.')
    expect(requestSpy).not.toHaveBeenCalled()
    act(() => root.unmount())
  })

  it('safely handles non-string or array values without throwing TypeError', async () => {
    expect(resolveDisplayUrl(null)).toBe('')
    expect(resolveDisplayUrl(undefined)).toBe('')
    expect(resolveDisplayUrl(['custom.mp3'] as any)).toBe('')
    expect(resolveDisplayUrl(123 as any)).toBe('')

    const { container: view } = await render(['https://example.com/sound.mp3'] as any, 'audio')
    expect(view).not.toBeNull()
  })
})

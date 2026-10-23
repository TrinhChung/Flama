// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MediaFieldPreview } from '@/entities/flashcard'

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
    return { container, onChange }
  }

  it('renders image preview by default and hides raw URL textarea in preview mode', async () => {
    const { container: view } = await render('https://example.com/cat.png')
    expect(view.querySelector('img')?.src).toBe('https://example.com/cat.png')
    // Raw URL textarea must NOT be visible in preview mode
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
    // In code mode, textarea is hidden and copy button is available
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

    // Simulate paste event with plain text URL
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

  it('rejects pasted images exceeding 2MB and does not send request', async () => {
    const { toast } = await import('sonner')
    const toastErrorSpy = vi.spyOn(toast, 'error')

    const onChange = vi.fn()
    const { container: view } = await render('', 'image', onChange)
    const previewContainer = view.querySelector('[tabindex="0"]') as HTMLDivElement

    const imageCompression = await import('@/lib/imageCompression')
    vi.spyOn(imageCompression, 'compressImage').mockRejectedValue(new Error('Mock compression error'))

    // Create an oversized file (3MB)
    const largeFile = new File([new ArrayBuffer(3 * 1024 * 1024)], 'huge.png', { type: 'image/png' })

    const pasteEvent = new Event('paste', { bubbles: true, cancelable: true }) as any
    pasteEvent.clipboardData = {
      items: [{
        type: 'image/png',
        getAsFile: () => largeFile,
      }],
      files: [largeFile],
      getData: () => '',
    }

    await act(async () => {
      previewContainer.dispatchEvent(pasteEvent)
    })

    expect(toastErrorSpy).toHaveBeenCalledWith('Dung lượng ảnh vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.')
    expect(onChange).not.toHaveBeenCalled()
  })
})

// @vitest-environment jsdom

import { act } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MediaFieldPreview } from './MediaFieldPreview'

describe('MediaFieldPreview', () => {
  let container: HTMLDivElement | null = null

  afterEach(() => {
    container?.remove()
    container = null
    document.body.replaceChildren()
  })

  async function render(value: string, fieldType: 'image' | 'audio' | 'diagram' = 'image') {
    container = document.createElement('div')
    document.body.appendChild(container)
    const root = createRoot(container)
    await act(async () => {
      root.render(
        <MediaFieldPreview
          fieldName={fieldType === 'audio' ? 'Audio' : 'Illustration'}
          fieldType={fieldType}
          value={value}
          onChange={vi.fn()}
        />,
      )
    })
    return container
  }

  it('renders image preview by default', async () => {
    const view = await render('https://example.com/cat.png')
    expect(view.querySelector('img')?.src).toBe('https://example.com/cat.png')
  })

  it('renders every newline-separated image URL', async () => {
    const view = await render('https://example.com/1.png\nhttps://example.com/2.png')
    expect(view.querySelectorAll('img')).toHaveLength(2)
  })

  it('shows derived HTML in code mode while keeping URL data editable', async () => {
    const view = await render('https://example.com/sound.mp3', 'audio')
    const codeButton = view.querySelector('button[title="Xem mã HTML"]') as HTMLButtonElement
    await act(async () => codeButton.click())

    expect(view.querySelector('pre')?.textContent).toContain(
      '<audio controls src="https://example.com/sound.mp3"></audio>',
    )
    expect((view.querySelector('textarea') as HTMLTextAreaElement).value).toBe(
      'https://example.com/sound.mp3',
    )

    const previewButton = view.querySelector('button[title="Xem trước"]') as HTMLButtonElement
    await act(async () => previewButton.click())
    expect(view.querySelector('audio')).not.toBeNull()
    expect(view.querySelector('textarea')).not.toBeNull()
  })

  it('does not invent a proxy URL for a bare legacy filename', async () => {
    const view = await render('legacy.mp3', 'audio')
    expect(view.querySelector('audio')).toBeNull()
    expect(view.textContent).toContain('1 dòng không phải URL media hợp lệ')
  })

  it('does not preview an obvious wrong-kind URL', async () => {
    const view = await render('https://example.com/picture.png', 'audio')
    expect(view.querySelector('audio')).toBeNull()
    expect(view.textContent).toContain('1 dòng không phải URL media hợp lệ')
  })

  it('rejects non-canonical managed paths and traversal segments', async () => {
    const view = await render('/media/library/../../secret.png\n/media/private/file.png')
    expect(view.querySelector('img')).toBeNull()
    expect(view.textContent).toContain('2 dòng không phải URL media hợp lệ')
  })

  it('renders an empty placeholder', async () => {
    const view = await render('', 'diagram')
    expect(view.textContent).toContain('Chưa có ảnh hợp lệ')
  })
})

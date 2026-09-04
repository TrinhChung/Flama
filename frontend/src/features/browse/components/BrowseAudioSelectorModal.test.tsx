// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act } from 'react'
import { createRoot, Root } from 'react-dom/client'
import { BrowseAudioSelectorModal } from './BrowseAudioSelectorModal'

describe('BrowseAudioSelectorModal', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => {
      root.unmount()
    })
    container.remove()
    document.body.innerHTML = ''
  })

  it('renders audio options and voice categories when isOpen is true', async () => {
    const onSelectWebVoiceVox = vi.fn()
    const onSelectLocalVoice = vi.fn()
    const onClose = vi.fn()

    await act(async () => {
      root.render(
        <BrowseAudioSelectorModal
          isOpen={true}
          onClose={onClose}
          onSelectWebVoiceVox={onSelectWebVoiceVox}
          onSelectLocalVoice={onSelectLocalVoice}
          selectedCardCount={5}
        />,
      )
    })

    // Dialog title
    expect(document.body.textContent).toContain('Tạo âm thanh phát âm')
    // Badge
    expect(document.body.textContent).toContain('5 thẻ')
    // Voice items
    expect(document.body.textContent).toContain('Web VoiceVox')
    expect(document.body.textContent).toContain('VoiceVox Local')
    expect(document.body.textContent).toContain('Tiếng Anh Local')
    expect(document.body.textContent).toContain('Tiếng Trung Local')
    expect(document.body.textContent).toContain('Tiếng Pháp Local')
  })

  it('triggers onSelectWebVoiceVox when Web VoiceVox is clicked', async () => {
    const onSelectWebVoiceVox = vi.fn()
    const onSelectLocalVoice = vi.fn()
    const onClose = vi.fn()

    await act(async () => {
      root.render(
        <BrowseAudioSelectorModal
          isOpen={true}
          onClose={onClose}
          onSelectWebVoiceVox={onSelectWebVoiceVox}
          onSelectLocalVoice={onSelectLocalVoice}
        />,
      )
    })

    const buttons = Array.from(document.body.querySelectorAll('button'))
    const webBtn = buttons.find((btn) => btn.textContent?.includes('Web VoiceVox'))
    expect(webBtn).toBeDefined()

    await act(async () => {
      webBtn?.click()
    })
    expect(onSelectWebVoiceVox).toHaveBeenCalledTimes(1)
  })

  it('triggers onSelectLocalVoice with proper engine and voiceId when local voices are clicked', async () => {
    const onSelectWebVoiceVox = vi.fn()
    const onSelectLocalVoice = vi.fn()
    const onClose = vi.fn()

    await act(async () => {
      root.render(
        <BrowseAudioSelectorModal
          isOpen={true}
          onClose={onClose}
          onSelectWebVoiceVox={onSelectWebVoiceVox}
          onSelectLocalVoice={onSelectLocalVoice}
        />,
      )
    })

    const buttons = Array.from(document.body.querySelectorAll('button'))

    // 1. VoiceVox Local
    const vvLocalBtn = buttons.find((btn) => btn.textContent?.includes('VoiceVox Local'))
    expect(vvLocalBtn).toBeDefined()
    await act(async () => {
      vvLocalBtn?.click()
    })
    expect(onSelectLocalVoice).toHaveBeenCalledWith('voicevox', '3')

    // 2. Kokoro English
    const enBtn = buttons.find((btn) => btn.textContent?.includes('Tiếng Anh Local'))
    expect(enBtn).toBeDefined()
    await act(async () => {
      enBtn?.click()
    })
    expect(onSelectLocalVoice).toHaveBeenCalledWith('kokoro', 'af_bella')
  })
})

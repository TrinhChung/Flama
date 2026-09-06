// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { BrowseTtsModal } from './BrowseTtsModal'
import type { useBrowseState } from '../hooks/useBrowseState'

describe('BrowseTtsModal', () => {
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

  function createMockBrowse(overrides: Partial<ReturnType<typeof useBrowseState>> = {}): ReturnType<typeof useBrowseState> {
    return {
      isTtsModalOpen: true,
      setIsTtsModalOpen: vi.fn(),
      ttsVoicesQuery: {
        data: {
          items: [
            { id: '2', label: '四国めたん (Metan) - ノーマル', speaker_name: '四国めたん', style_name: 'ノーマル' },
            { id: '8', label: '春日部つむぎ (Tsumugi) - ノーマル', speaker_name: '春日部つむぎ', style_name: 'ノーマル' },
          ],
        },
        isPending: false,
      } as any,
      ttsApiKey: 'test-key',
      setTtsApiKey: vi.fn(),
      showApiKey: false,
      setShowApiKey: vi.fn(),
      isKeySaved: true,
      isSavingKey: false,
      saveApiKeyIfValid: vi.fn(),
      ttsCharacter: '8',
      setTtsCharacter: vi.fn(),
      ttsSourceField: 'CustomWord',
      setTtsSourceField: vi.fn(),
      ttsDestinationField: 'CustomAudio',
      setTtsDestinationField: vi.fn(),
      ttsVolumeScale: 1.2,
      setTtsVolumeScale: vi.fn(),
      ttsPitch: 0.05,
      setTtsPitch: vi.fn(),
      ttsSpeed: 1.15,
      setTtsSpeed: vi.fn(),
      ttsIntonationScale: 1.1,
      setTtsIntonationScale: vi.fn(),
      ttsInitialSilence: 0.1,
      setTtsInitialSilence: vi.fn(),
      ttsFinalSilence: 0.1,
      setTtsFinalSilence: vi.fn(),
      ttsAppendAudio: false,
      setTtsAppendAudio: vi.fn(),
      ttsUseOpus: true,
      setTtsUseOpus: vi.fn(),
      handlePreviewVoiceVox: vi.fn(),
      handleResetTtsDefaults: vi.fn(),
      generateTtsMutation: { mutate: vi.fn(), isPending: false } as any,
      targetTtsCardIds: ['c1'],
      selectedCards: ['c1'],
      selectedDeckId: 1,
      selectedDeck: null,
      cards: [],
      isPreviewing: false,
      availableSourceFieldNames: ['Reading', 'CustomWord'],
      availableAudioFieldNames: ['Audio', 'CustomAudio'],
      ...overrides,
    } as unknown as ReturnType<typeof useBrowseState>
  }

  it('renders with preserved character and custom source and destination fields', async () => {
    const mockBrowse = createMockBrowse()

    await act(async () => {
      root.render(<BrowseTtsModal browse={mockBrowse} />)
    })

    expect(document.body.textContent).toContain('Tạo âm thanh đọc thẻ (VoiceVox Web Service)')

    // Character select should reflect ttsCharacter
    const charSelect = document.getElementById('voicevox-character') as HTMLSelectElement | null
    expect(charSelect).not.toBeNull()
    expect(charSelect?.value).toBe('8')

    // Source field select should reflect ttsSourceField
    const sourceSelect = document.getElementById('tts-source-field') as HTMLSelectElement | null
    expect(sourceSelect).not.toBeNull()
    expect(sourceSelect?.value).toBe('CustomWord')

    // Destination field select should reflect ttsDestinationField
    const destSelect = document.getElementById('tts-dest-field') as HTMLSelectElement | null
    expect(destSelect).not.toBeNull()
    expect(destSelect?.value).toBe('CustomAudio')
  })

  it('preserves placeholder option when voices query is still pending', async () => {
    const mockBrowse = createMockBrowse({
      ttsCharacter: '14',
      ttsVoicesQuery: {
        data: undefined,
        isPending: true,
      } as any,
    })

    await act(async () => {
      root.render(<BrowseTtsModal browse={mockBrowse} />)
    })

    const charSelect = document.getElementById('voicevox-character') as HTMLSelectElement | null
    expect(charSelect).not.toBeNull()
    expect(charSelect?.value).toBe('14')
  })
})

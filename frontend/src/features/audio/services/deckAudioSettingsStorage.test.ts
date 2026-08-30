// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_DECK_AUDIO_STUDIO_SETTINGS,
  loadStoredDeckAudioStudioSettings,
  resetStoredDeckAudioStudioSettings,
  saveStoredDeckAudioStudioSettings,
} from './deckAudioSettingsStorage'

describe('deckAudioSettingsStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('loads default deck audio studio settings when storage is empty', () => {
    const settings = loadStoredDeckAudioStudioSettings()
    expect(settings).toEqual(DEFAULT_DECK_AUDIO_STUDIO_SETTINGS)
  })

  it('saves and loads customized studio settings', () => {
    saveStoredDeckAudioStudioSettings({
      generationMode: 'all',
      defaultEngineId: 'kokoro',
      defaultVoiceIdKokoro: 'zm_yunjian',
      volume: 1.2,
      pitch: 0.1,
      speed: 1.15,
      intonation: 1.25,
    })

    const loaded = loadStoredDeckAudioStudioSettings()
    expect(loaded.generationMode).toBe('all')
    expect(loaded.defaultEngineId).toBe('kokoro')
    expect(loaded.defaultVoiceIdKokoro).toBe('zm_yunjian')
    expect(loaded.volume).toBe(1.2)
    expect(loaded.pitch).toBe(0.1)
    expect(loaded.speed).toBe(1.15)
    expect(loaded.intonation).toBe(1.25)
  })

  it('resets deck audio studio settings to defaults', () => {
    saveStoredDeckAudioStudioSettings({ generationMode: 'all', volume: 1.8 })
    resetStoredDeckAudioStudioSettings()
    const loaded = loadStoredDeckAudioStudioSettings()
    expect(loaded).toEqual(DEFAULT_DECK_AUDIO_STUDIO_SETTINGS)
  })
})

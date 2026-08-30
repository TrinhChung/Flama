// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_BROWSE_TTS_SETTINGS,
  loadStoredBrowseTtsSettings,
  resetStoredBrowseTtsSettings,
  saveStoredBrowseTtsSettings,
} from './ttsSettingsStorage'

describe('ttsSettingsStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('loads default browse TTS settings when storage is empty', () => {
    const settings = loadStoredBrowseTtsSettings()
    expect(settings).toEqual(DEFAULT_BROWSE_TTS_SETTINGS)
  })

  it('saves and loads customized browse TTS settings', () => {
    saveStoredBrowseTtsSettings({
      character: '3',
      volumeScale: 1.25,
      pitch: 0.05,
      speed: 1.1,
      intonationScale: 1.2,
      initialSilence: 0.2,
      finalSilence: 0.3,
      appendAudio: true,
      useOpus: true,
    })

    const loaded = loadStoredBrowseTtsSettings()
    expect(loaded.character).toBe('3')
    expect(loaded.volumeScale).toBe(1.25)
    expect(loaded.pitch).toBe(0.05)
    expect(loaded.speed).toBe(1.1)
    expect(loaded.intonationScale).toBe(1.2)
    expect(loaded.initialSilence).toBe(0.2)
    expect(loaded.finalSilence).toBe(0.3)
    expect(loaded.appendAudio).toBe(true)
    expect(loaded.useOpus).toBe(true)
  })

  it('clamps out of range numbers', () => {
    saveStoredBrowseTtsSettings({
      volumeScale: 99,
      pitch: -1,
      speed: 0.1,
    })

    const loaded = loadStoredBrowseTtsSettings()
    expect(loaded.volumeScale).toBe(2)
    expect(loaded.pitch).toBe(-0.15)
    expect(loaded.speed).toBe(0.5)
  })

  it('resets browse TTS settings to defaults', () => {
    saveStoredBrowseTtsSettings({ character: '14', speed: 1.3 })
    resetStoredBrowseTtsSettings()
    const loaded = loadStoredBrowseTtsSettings()
    expect(loaded).toEqual(DEFAULT_BROWSE_TTS_SETTINGS)
  })
})

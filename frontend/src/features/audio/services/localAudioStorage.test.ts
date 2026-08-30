// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_LOCAL_AUDIO_SETTINGS,
  loadStoredLocalAudioSettings,
  resetStoredLocalAudioSettings,
  saveStoredLocalAudioSettings,
} from './localAudioStorage'

describe('localAudioStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('loads default local audio settings when storage is empty', () => {
    const settings = loadStoredLocalAudioSettings()
    expect(settings).toEqual(DEFAULT_LOCAL_AUDIO_SETTINGS)
  })

  it('saves and loads customized local audio settings', () => {
    saveStoredLocalAudioSettings({
      lastVoiceIdVoicevox: '14',
      lastVoiceIdKokoro: 'zf_xiaobei',
      volumeScale: 1.5,
      pitch: 0.1,
      speed: 1.2,
      intonationScale: 1.3,
    })

    const loaded = loadStoredLocalAudioSettings()
    expect(loaded.lastVoiceIdVoicevox).toBe('14')
    expect(loaded.lastVoiceIdKokoro).toBe('zf_xiaobei')
    expect(loaded.volumeScale).toBe(1.5)
    expect(loaded.pitch).toBe(0.1)
    expect(loaded.speed).toBe(1.2)
    expect(loaded.intonationScale).toBe(1.3)
  })

  it('clamps out of range numbers', () => {
    saveStoredLocalAudioSettings({
      volumeScale: 10,
      pitch: -5,
      speed: 10,
      intonationScale: -2,
    })

    const loaded = loadStoredLocalAudioSettings()
    expect(loaded.volumeScale).toBe(2)
    expect(loaded.pitch).toBe(-0.4)
    expect(loaded.speed).toBe(4.0)
    expect(loaded.intonationScale).toBe(0)
  })

  it('resets local audio settings to defaults', () => {
    saveStoredLocalAudioSettings({ lastVoiceIdVoicevox: '8', speed: 2.0 })
    resetStoredLocalAudioSettings()
    const loaded = loadStoredLocalAudioSettings()
    expect(loaded).toEqual(DEFAULT_LOCAL_AUDIO_SETTINGS)
  })
})

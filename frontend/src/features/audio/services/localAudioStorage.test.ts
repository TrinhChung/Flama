// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_LOCAL_AUDIO_SETTINGS,
  getLanguageGroupFromVoiceId,
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

  it('resolves correct language groups from Kokoro voice IDs', () => {
    expect(getLanguageGroupFromVoiceId('af_bella')).toBe('en')
    expect(getLanguageGroupFromVoiceId('bm_george')).toBe('en')
    expect(getLanguageGroupFromVoiceId('zf_xiaobei')).toBe('zh')
    expect(getLanguageGroupFromVoiceId('zm_yunjian')).toBe('zh')
    expect(getLanguageGroupFromVoiceId('ef_dora')).toBe('es')
    expect(getLanguageGroupFromVoiceId('ff_siwis')).toBe('fr')
    expect(getLanguageGroupFromVoiceId('if_sara')).toBe('it')
    expect(getLanguageGroupFromVoiceId('pf_dora')).toBe('pt')
    expect(getLanguageGroupFromVoiceId('hf_alpha')).toBe('hi')
  })

  it('saves and loads customized local audio settings', () => {
    saveStoredLocalAudioSettings({
      lastVoiceIdVoicevox: '14',
      lastVoiceIdKokoro: 'zf_xiaobei',
      volumeScale: 1.5,
      pitch: 0.1,
      speed: 1.2,
      intonationScale: 1.3,
      sourceField: 'Word',
      destinationField: 'AudioWord',
    })

    const loaded = loadStoredLocalAudioSettings()
    expect(loaded.lastVoiceIdVoicevox).toBe('14')
    expect(loaded.lastVoiceIdKokoro).toBe('zf_xiaobei')
    expect(loaded.volumeScale).toBe(1.5)
    expect(loaded.pitch).toBe(0.1)
    expect(loaded.speed).toBe(1.2)
    expect(loaded.intonationScale).toBe(1.3)
    expect(loaded.sourceField).toBe('Word')
    expect(loaded.destinationField).toBe('AudioWord')
  })

  it('persists Kokoro voices independently across different languages', () => {
    saveStoredLocalAudioSettings({
      lastVoiceIdKokoro: 'am_adam',
      lastVoiceIdKokoroByLang: {
        en: 'am_adam',
      },
    })

    saveStoredLocalAudioSettings({
      lastVoiceIdKokoro: 'zm_yunjian',
      lastVoiceIdKokoroByLang: {
        zh: 'zm_yunjian',
      },
    })

    const loaded = loadStoredLocalAudioSettings()
    expect(loaded.lastVoiceIdKokoroByLang?.en).toBe('am_adam')
    expect(loaded.lastVoiceIdKokoroByLang?.zh).toBe('zm_yunjian')
  })

  it('stores engine-specific speeds and note-type field mappings independently', () => {
    saveStoredLocalAudioSettings({
      speedVoicevox: 0.95,
      speedKokoro: 1.15,
      fieldMappingByNoteType: {
        'Chinese Note': { sourceField: 'Hanzi', destinationField: 'Audio' },
        'Japanese Note': { sourceField: 'Reading', destinationField: 'AudioReading' },
      },
    })

    const loaded = loadStoredLocalAudioSettings()
    expect(loaded.speedVoicevox).toBe(0.95)
    expect(loaded.speedKokoro).toBe(1.15)
    expect(loaded.fieldMappingByNoteType?.['Chinese Note']).toEqual({
      sourceField: 'Hanzi',
      destinationField: 'Audio',
    })
    expect(loaded.fieldMappingByNoteType?.['Japanese Note']).toEqual({
      sourceField: 'Reading',
      destinationField: 'AudioReading',
    })
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

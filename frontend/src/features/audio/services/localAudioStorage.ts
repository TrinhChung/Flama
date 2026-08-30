export interface LocalAudioSettings {
  lastVoiceIdVoicevox: string
  lastVoiceIdKokoro: string
  volumeScale: number
  pitch: number
  speed: number
  intonationScale: number
}

export const DEFAULT_LOCAL_AUDIO_SETTINGS: LocalAudioSettings = {
  lastVoiceIdVoicevox: '3', // Zundamon Normal
  lastVoiceIdKokoro: 'af_bella', // Bella US Female
  volumeScale: 1.0,
  pitch: 0.0,
  speed: 1.0,
  intonationScale: 1.0,
}

const LOCAL_AUDIO_STORAGE_KEY = 'flama_local_audio_settings_v1'

export function loadStoredLocalAudioSettings(): LocalAudioSettings {
  try {
    const raw = localStorage.getItem(LOCAL_AUDIO_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_LOCAL_AUDIO_SETTINGS }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return { ...DEFAULT_LOCAL_AUDIO_SETTINGS }
    }

    return {
      lastVoiceIdVoicevox: typeof parsed.lastVoiceIdVoicevox === 'string' && parsed.lastVoiceIdVoicevox.trim()
        ? parsed.lastVoiceIdVoicevox.trim()
        : DEFAULT_LOCAL_AUDIO_SETTINGS.lastVoiceIdVoicevox,
      lastVoiceIdKokoro: typeof parsed.lastVoiceIdKokoro === 'string' && parsed.lastVoiceIdKokoro.trim()
        ? parsed.lastVoiceIdKokoro.trim()
        : DEFAULT_LOCAL_AUDIO_SETTINGS.lastVoiceIdKokoro,
      volumeScale: typeof parsed.volumeScale === 'number' && !isNaN(parsed.volumeScale)
        ? Math.max(0, Math.min(2, parsed.volumeScale))
        : DEFAULT_LOCAL_AUDIO_SETTINGS.volumeScale,
      pitch: typeof parsed.pitch === 'number' && !isNaN(parsed.pitch)
        ? Math.max(-0.4, Math.min(0.4, parsed.pitch))
        : DEFAULT_LOCAL_AUDIO_SETTINGS.pitch,
      speed: typeof parsed.speed === 'number' && !isNaN(parsed.speed)
        ? Math.max(0.1, Math.min(4.0, parsed.speed))
        : DEFAULT_LOCAL_AUDIO_SETTINGS.speed,
      intonationScale: typeof parsed.intonationScale === 'number' && !isNaN(parsed.intonationScale)
        ? Math.max(0, Math.min(2, parsed.intonationScale))
        : DEFAULT_LOCAL_AUDIO_SETTINGS.intonationScale,
    }
  } catch {
    return { ...DEFAULT_LOCAL_AUDIO_SETTINGS }
  }
}

export function saveStoredLocalAudioSettings(settings: Partial<LocalAudioSettings>): void {
  try {
    const current = loadStoredLocalAudioSettings()
    const updated: LocalAudioSettings = {
      ...current,
      ...settings,
    }
    localStorage.setItem(LOCAL_AUDIO_STORAGE_KEY, JSON.stringify(updated))
  } catch (err) {
    console.error('Failed to save local audio settings to localStorage:', err)
  }
}

export function resetStoredLocalAudioSettings(): void {
  try {
    localStorage.removeItem(LOCAL_AUDIO_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to reset local audio settings in localStorage:', err)
  }
}

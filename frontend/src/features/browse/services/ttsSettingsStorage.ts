export interface BrowseTtsSettings {
  character: string
  volumeScale: number
  pitch: number
  speed: number
  intonationScale: number
  initialSilence: number
  finalSilence: number
  appendAudio: boolean
  useOpus: boolean
}

export const DEFAULT_BROWSE_TTS_SETTINGS: BrowseTtsSettings = {
  character: '',
  volumeScale: 1.0,
  pitch: 0.0,
  speed: 1.0,
  intonationScale: 1.0,
  initialSilence: 0.1,
  finalSilence: 0.1,
  appendAudio: false,
  useOpus: false,
}

const BROWSE_TTS_STORAGE_KEY = 'flama_voicevox_tts_settings_v1'

export function loadStoredBrowseTtsSettings(): BrowseTtsSettings {
  try {
    const raw = localStorage.getItem(BROWSE_TTS_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_BROWSE_TTS_SETTINGS }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return { ...DEFAULT_BROWSE_TTS_SETTINGS }
    }

    return {
      character: typeof parsed.character === 'string' ? parsed.character : DEFAULT_BROWSE_TTS_SETTINGS.character,
      volumeScale: typeof parsed.volumeScale === 'number' && !isNaN(parsed.volumeScale)
        ? Math.max(0, Math.min(2, parsed.volumeScale))
        : DEFAULT_BROWSE_TTS_SETTINGS.volumeScale,
      pitch: typeof parsed.pitch === 'number' && !isNaN(parsed.pitch)
        ? Math.max(-0.15, Math.min(0.15, parsed.pitch))
        : DEFAULT_BROWSE_TTS_SETTINGS.pitch,
      speed: typeof parsed.speed === 'number' && !isNaN(parsed.speed)
        ? Math.max(0.5, Math.min(1.5, parsed.speed))
        : DEFAULT_BROWSE_TTS_SETTINGS.speed,
      intonationScale: typeof parsed.intonationScale === 'number' && !isNaN(parsed.intonationScale)
        ? Math.max(0, Math.min(2, parsed.intonationScale))
        : DEFAULT_BROWSE_TTS_SETTINGS.intonationScale,
      initialSilence: typeof parsed.initialSilence === 'number' && !isNaN(parsed.initialSilence)
        ? Math.max(0, Math.min(1.5, parsed.initialSilence))
        : DEFAULT_BROWSE_TTS_SETTINGS.initialSilence,
      finalSilence: typeof parsed.finalSilence === 'number' && !isNaN(parsed.finalSilence)
        ? Math.max(0, Math.min(1.5, parsed.finalSilence))
        : DEFAULT_BROWSE_TTS_SETTINGS.finalSilence,
      appendAudio: typeof parsed.appendAudio === 'boolean' ? parsed.appendAudio : DEFAULT_BROWSE_TTS_SETTINGS.appendAudio,
      useOpus: typeof parsed.useOpus === 'boolean' ? parsed.useOpus : DEFAULT_BROWSE_TTS_SETTINGS.useOpus,
    }
  } catch {
    return { ...DEFAULT_BROWSE_TTS_SETTINGS }
  }
}

export function saveStoredBrowseTtsSettings(settings: Partial<BrowseTtsSettings>): void {
  try {
    const current = loadStoredBrowseTtsSettings()
    const updated: BrowseTtsSettings = {
      ...current,
      ...settings,
    }
    localStorage.setItem(BROWSE_TTS_STORAGE_KEY, JSON.stringify(updated))
  } catch (err) {
    console.error('Failed to save browse TTS settings to localStorage:', err)
  }
}

export function resetStoredBrowseTtsSettings(): void {
  try {
    localStorage.removeItem(BROWSE_TTS_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to reset browse TTS settings in localStorage:', err)
  }
}

export interface DeckAudioStudioSettings {
  generationMode: 'missing_and_broken' | 'all'
  defaultEngineId: 'voicevox' | 'kokoro'
  defaultVoiceIdVoicevox: string
  defaultVoiceIdKokoro: string
  volume: number
  pitch: number
  speed: number
  intonation: number
}

export const DEFAULT_DECK_AUDIO_STUDIO_SETTINGS: DeckAudioStudioSettings = {
  generationMode: 'missing_and_broken',
  defaultEngineId: 'voicevox',
  defaultVoiceIdVoicevox: '3', // Zundamon normal
  defaultVoiceIdKokoro: 'af_bella', // Bella US Female
  volume: 1.0,
  pitch: 0.0,
  speed: 1.0,
  intonation: 1.0,
}

const DECK_AUDIO_STUDIO_STORAGE_KEY = 'flama_deck_audio_studio_settings_v1'

export function loadStoredDeckAudioStudioSettings(): DeckAudioStudioSettings {
  try {
    const raw = localStorage.getItem(DECK_AUDIO_STUDIO_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_DECK_AUDIO_STUDIO_SETTINGS }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return { ...DEFAULT_DECK_AUDIO_STUDIO_SETTINGS }
    }

    return {
      generationMode: parsed.generationMode === 'all' ? 'all' : 'missing_and_broken',
      defaultEngineId: parsed.defaultEngineId === 'kokoro' ? 'kokoro' : 'voicevox',
      defaultVoiceIdVoicevox: typeof parsed.defaultVoiceIdVoicevox === 'string' && parsed.defaultVoiceIdVoicevox.trim()
        ? parsed.defaultVoiceIdVoicevox.trim()
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.defaultVoiceIdVoicevox,
      defaultVoiceIdKokoro: typeof parsed.defaultVoiceIdKokoro === 'string' && parsed.defaultVoiceIdKokoro.trim()
        ? parsed.defaultVoiceIdKokoro.trim()
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.defaultVoiceIdKokoro,
      volume: typeof parsed.volume === 'number' && !isNaN(parsed.volume)
        ? Math.max(0, Math.min(2, parsed.volume))
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.volume,
      pitch: typeof parsed.pitch === 'number' && !isNaN(parsed.pitch)
        ? Math.max(-0.4, Math.min(0.4, parsed.pitch))
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.pitch,
      speed: typeof parsed.speed === 'number' && !isNaN(parsed.speed)
        ? Math.max(0.1, Math.min(4.0, parsed.speed))
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.speed,
      intonation: typeof parsed.intonation === 'number' && !isNaN(parsed.intonation)
        ? Math.max(0, Math.min(2, parsed.intonation))
        : DEFAULT_DECK_AUDIO_STUDIO_SETTINGS.intonation,
    }
  } catch {
    return { ...DEFAULT_DECK_AUDIO_STUDIO_SETTINGS }
  }
}

export function saveStoredDeckAudioStudioSettings(settings: Partial<DeckAudioStudioSettings>): void {
  try {
    const current = loadStoredDeckAudioStudioSettings()
    const updated: DeckAudioStudioSettings = {
      ...current,
      ...settings,
    }
    localStorage.setItem(DECK_AUDIO_STUDIO_STORAGE_KEY, JSON.stringify(updated))
  } catch (err) {
    console.error('Failed to save deck audio studio settings to localStorage:', err)
  }
}

export function resetStoredDeckAudioStudioSettings(): void {
  try {
    localStorage.removeItem(DECK_AUDIO_STUDIO_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to reset deck audio studio settings in localStorage:', err)
  }
}

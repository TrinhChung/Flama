export interface LocalAudioSettings {
  lastVoiceIdVoicevox: string
  lastVoiceIdKokoro: string
  lastVoiceIdKokoroByLang?: Record<string, string>
  speedVoicevox?: number
  speedKokoro?: number
  pitchVoicevox?: number
  pitchKokoro?: number
  volumeScaleVoicevox?: number
  volumeScaleKokoro?: number
  intonationScaleVoicevox?: number
  intonationScaleKokoro?: number
  volumeScale: number
  pitch: number
  speed: number
  intonationScale: number
  sourceField?: string
  destinationField?: string
  fieldMappingByNoteType?: Record<string, { sourceField?: string; destinationField?: string }>
}

export const DEFAULT_LOCAL_AUDIO_SETTINGS: LocalAudioSettings = {
  lastVoiceIdVoicevox: '3', // Zundamon Normal
  lastVoiceIdKokoro: 'af_bella', // Bella US Female
  lastVoiceIdKokoroByLang: {
    en: 'af_bella',
    zh: 'zf_xiaobei',
    es: 'ef_dora',
    fr: 'ff_siwis',
    it: 'if_sara',
    pt: 'pf_dora',
    hi: 'hf_alpha',
  },
  volumeScale: 1.0,
  pitch: 0.0,
  speed: 1.0,
  intonationScale: 1.0,
  speedVoicevox: 1.0,
  speedKokoro: 1.0,
  pitchVoicevox: 0.0,
  pitchKokoro: 0.0,
  volumeScaleVoicevox: 1.0,
  volumeScaleKokoro: 1.0,
  intonationScaleVoicevox: 1.0,
  intonationScaleKokoro: 1.0,
  sourceField: 'Reading',
  destinationField: 'Audio',
  fieldMappingByNoteType: {},
}

const LOCAL_AUDIO_STORAGE_KEY = 'flama_local_audio_settings_v1'

export function getLanguageGroupFromVoiceId(voiceId: string): string {
  if (!voiceId) return 'en'
  const prefix = voiceId[0].toLowerCase()
  switch (prefix) {
    case 'a':
    case 'b':
      return 'en'
    case 'z':
      return 'zh'
    case 'e':
      return 'es'
    case 'f':
      return 'fr'
    case 'i':
      return 'it'
    case 'p':
      return 'pt'
    case 'h':
      return 'hi'
    default:
      return 'en'
  }
}

function sanitizeNumber(val: unknown, min: number, max: number, fallback: number): number {
  if (typeof val === 'number' && !isNaN(val)) {
    return Math.max(min, Math.min(max, val))
  }
  return fallback
}

function sanitizeStringRecord(obj: unknown): Record<string, string> {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return {}
  const res: Record<string, string> = {}
  for (const [k, v] of Object.entries(obj)) {
    if (typeof v === 'string' && v.trim()) {
      res[k] = v.trim()
    }
  }
  return res
}

function sanitizeFieldMappingRecord(obj: unknown): Record<string, { sourceField?: string; destinationField?: string }> {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return {}
  const res: Record<string, { sourceField?: string; destinationField?: string }> = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const entry: { sourceField?: string; destinationField?: string } = {}
      if (typeof (v as { sourceField?: unknown }).sourceField === 'string') {
        entry.sourceField = ((v as { sourceField: string }).sourceField || '').trim()
      }
      if (typeof (v as { destinationField?: unknown }).destinationField === 'string') {
        entry.destinationField = ((v as { destinationField: string }).destinationField || '').trim()
      }
      res[k] = entry
    }
  }
  return res
}

export function loadStoredLocalAudioSettings(): LocalAudioSettings {
  try {
    const raw = localStorage.getItem(LOCAL_AUDIO_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_LOCAL_AUDIO_SETTINGS }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return { ...DEFAULT_LOCAL_AUDIO_SETTINGS }
    }

    const lastVoiceIdVoicevox = typeof parsed.lastVoiceIdVoicevox === 'string' && parsed.lastVoiceIdVoicevox.trim()
      ? parsed.lastVoiceIdVoicevox.trim()
      : DEFAULT_LOCAL_AUDIO_SETTINGS.lastVoiceIdVoicevox

    const lastVoiceIdKokoro = typeof parsed.lastVoiceIdKokoro === 'string' && parsed.lastVoiceIdKokoro.trim()
      ? parsed.lastVoiceIdKokoro.trim()
      : DEFAULT_LOCAL_AUDIO_SETTINGS.lastVoiceIdKokoro

    const parsedKokoroByLang = sanitizeStringRecord(parsed.lastVoiceIdKokoroByLang)
    const lastVoiceIdKokoroByLang = {
      ...DEFAULT_LOCAL_AUDIO_SETTINGS.lastVoiceIdKokoroByLang,
      ...parsedKokoroByLang,
    }
    const currentLang = getLanguageGroupFromVoiceId(lastVoiceIdKokoro)
    if (lastVoiceIdKokoro && !lastVoiceIdKokoroByLang[currentLang]) {
      lastVoiceIdKokoroByLang[currentLang] = lastVoiceIdKokoro
    }

    const volumeScale = sanitizeNumber(parsed.volumeScale, 0, 2, DEFAULT_LOCAL_AUDIO_SETTINGS.volumeScale)
    const pitch = sanitizeNumber(parsed.pitch, -0.4, 0.4, DEFAULT_LOCAL_AUDIO_SETTINGS.pitch)
    const speed = sanitizeNumber(parsed.speed, 0.1, 4.0, DEFAULT_LOCAL_AUDIO_SETTINGS.speed)
    const intonationScale = sanitizeNumber(parsed.intonationScale, 0, 2, DEFAULT_LOCAL_AUDIO_SETTINGS.intonationScale)

    const speedVoicevox = typeof parsed.speedVoicevox === 'number'
      ? sanitizeNumber(parsed.speedVoicevox, 0.1, 4.0, speed)
      : speed
    const speedKokoro = typeof parsed.speedKokoro === 'number'
      ? sanitizeNumber(parsed.speedKokoro, 0.1, 4.0, speed)
      : speed

    const pitchVoicevox = typeof parsed.pitchVoicevox === 'number'
      ? sanitizeNumber(parsed.pitchVoicevox, -0.4, 0.4, pitch)
      : pitch
    const pitchKokoro = typeof parsed.pitchKokoro === 'number'
      ? sanitizeNumber(parsed.pitchKokoro, -0.4, 0.4, pitch)
      : pitch

    const volumeScaleVoicevox = typeof parsed.volumeScaleVoicevox === 'number'
      ? sanitizeNumber(parsed.volumeScaleVoicevox, 0, 2, volumeScale)
      : volumeScale
    const volumeScaleKokoro = typeof parsed.volumeScaleKokoro === 'number'
      ? sanitizeNumber(parsed.volumeScaleKokoro, 0, 2, volumeScale)
      : volumeScale

    const intonationScaleVoicevox = typeof parsed.intonationScaleVoicevox === 'number'
      ? sanitizeNumber(parsed.intonationScaleVoicevox, 0, 2, intonationScale)
      : intonationScale
    const intonationScaleKokoro = typeof parsed.intonationScaleKokoro === 'number'
      ? sanitizeNumber(parsed.intonationScaleKokoro, 0, 2, intonationScale)
      : intonationScale

    const sourceField = typeof parsed.sourceField === 'string' && parsed.sourceField.trim()
      ? parsed.sourceField.trim()
      : DEFAULT_LOCAL_AUDIO_SETTINGS.sourceField

    const destinationField = typeof parsed.destinationField === 'string' && parsed.destinationField.trim()
      ? parsed.destinationField.trim()
      : DEFAULT_LOCAL_AUDIO_SETTINGS.destinationField

    const fieldMappingByNoteType = sanitizeFieldMappingRecord(parsed.fieldMappingByNoteType)

    return {
      lastVoiceIdVoicevox,
      lastVoiceIdKokoro,
      lastVoiceIdKokoroByLang,
      volumeScale,
      pitch,
      speed,
      intonationScale,
      speedVoicevox,
      speedKokoro,
      pitchVoicevox,
      pitchKokoro,
      volumeScaleVoicevox,
      volumeScaleKokoro,
      intonationScaleVoicevox,
      intonationScaleKokoro,
      sourceField,
      destinationField,
      fieldMappingByNoteType,
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
      lastVoiceIdKokoroByLang: {
        ...(current.lastVoiceIdKokoroByLang || {}),
        ...(settings.lastVoiceIdKokoroByLang || {}),
      },
      fieldMappingByNoteType: {
        ...(current.fieldMappingByNoteType || {}),
        ...(settings.fieldMappingByNoteType || {}),
      },
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

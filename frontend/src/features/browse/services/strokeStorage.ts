export interface StrokeSettings {
  locale: 'ja' | 'zh-CN' | 'zh-TW'
  outputFormat: 'html' | 'raw' | 'urls'
  overwrite: boolean
}

export const DEFAULT_STROKE_SETTINGS: StrokeSettings = {
  locale: 'ja',
  outputFormat: 'html',
  overwrite: false,
}

const STROKE_STORAGE_KEY = 'flama_browse_stroke_settings_v1'

const VALID_LOCALES = new Set(['ja', 'zh-CN', 'zh-TW'])
const VALID_FORMATS = new Set(['html', 'raw', 'urls'])

export function loadStoredStrokeSettings(): StrokeSettings {
  try {
    const raw = localStorage.getItem(STROKE_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_STROKE_SETTINGS }

    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') {
      return { ...DEFAULT_STROKE_SETTINGS }
    }

    return {
      locale: VALID_LOCALES.has(parsed.locale) ? parsed.locale : DEFAULT_STROKE_SETTINGS.locale,
      outputFormat: VALID_FORMATS.has(parsed.outputFormat) ? parsed.outputFormat : DEFAULT_STROKE_SETTINGS.outputFormat,
      overwrite: typeof parsed.overwrite === 'boolean' ? parsed.overwrite : DEFAULT_STROKE_SETTINGS.overwrite,
    }
  } catch {
    return { ...DEFAULT_STROKE_SETTINGS }
  }
}

export function saveStoredStrokeSettings(settings: Partial<StrokeSettings>): void {
  try {
    const current = loadStoredStrokeSettings()
    const updated: StrokeSettings = {
      ...current,
      ...settings,
    }
    localStorage.setItem(STROKE_STORAGE_KEY, JSON.stringify(updated))
  } catch (err) {
    console.error('Failed to save stroke settings to localStorage:', err)
  }
}

export function resetStoredStrokeSettings(): void {
  try {
    localStorage.removeItem(STROKE_STORAGE_KEY)
  } catch (err) {
    console.error('Failed to reset stroke settings in localStorage:', err)
  }
}

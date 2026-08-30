// @vitest-environment jsdom

import { beforeEach, describe, expect, it } from 'vitest'
import {
  DEFAULT_STROKE_SETTINGS,
  loadStoredStrokeSettings,
  resetStoredStrokeSettings,
  saveStoredStrokeSettings,
} from './strokeStorage'

describe('strokeStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('loads default stroke settings when storage is empty', () => {
    const settings = loadStoredStrokeSettings()
    expect(settings).toEqual(DEFAULT_STROKE_SETTINGS)
  })

  it('saves and loads customized stroke settings', () => {
    saveStoredStrokeSettings({
      locale: 'zh-CN',
      outputFormat: 'raw',
      overwrite: true,
    })

    const loaded = loadStoredStrokeSettings()
    expect(loaded.locale).toBe('zh-CN')
    expect(loaded.outputFormat).toBe('raw')
    expect(loaded.overwrite).toBe(true)
  })

  it('partially updates settings while preserving other fields', () => {
    saveStoredStrokeSettings({ locale: 'zh-TW' })
    let loaded = loadStoredStrokeSettings()
    expect(loaded.locale).toBe('zh-TW')
    expect(loaded.outputFormat).toBe('html')
    expect(loaded.overwrite).toBe(false)

    saveStoredStrokeSettings({ outputFormat: 'urls', overwrite: true })
    loaded = loadStoredStrokeSettings()
    expect(loaded.locale).toBe('zh-TW')
    expect(loaded.outputFormat).toBe('urls')
    expect(loaded.overwrite).toBe(true)
  })

  it('resets stroke settings to defaults', () => {
    saveStoredStrokeSettings({ locale: 'zh-CN', overwrite: true })
    resetStoredStrokeSettings()
    const loaded = loadStoredStrokeSettings()
    expect(loaded).toEqual(DEFAULT_STROKE_SETTINGS)
  })
})

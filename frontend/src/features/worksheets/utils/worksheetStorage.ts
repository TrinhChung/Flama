import type { WorksheetFieldMapping, WorksheetLayoutOptions } from '../types'

export interface WorksheetNoteTypePreset {
  noteTypeId: string | number
  fieldMapping: WorksheetFieldMapping
  templateId?: string
  layoutOptions?: Partial<WorksheetLayoutOptions>
  updatedAt: number
}

const STORAGE_PREFIX = 'flama_worksheet_preset_notetype_'

export function getWorksheetPresetKey(noteTypeId: string | number): string {
  return `${STORAGE_PREFIX}${noteTypeId}`
}

export function loadWorksheetPreset(noteTypeId: string | number): WorksheetNoteTypePreset | null {
  if (typeof window === 'undefined' || !noteTypeId) return null
  try {
    const raw = localStorage.getItem(getWorksheetPresetKey(noteTypeId))
    if (!raw) return null
    return JSON.parse(raw) as WorksheetNoteTypePreset
  } catch (err) {
    console.warn('Failed to load worksheet preset for note type:', noteTypeId, err)
    return null
  }
}

export function saveWorksheetPreset(
  noteTypeId: string | number,
  data: {
    fieldMapping: WorksheetFieldMapping
    templateId?: string
    layoutOptions?: Partial<WorksheetLayoutOptions>
  },
): void {
  if (typeof window === 'undefined' || !noteTypeId) return
  try {
    const payload: WorksheetNoteTypePreset = {
      noteTypeId,
      fieldMapping: data.fieldMapping,
      templateId: data.templateId,
      layoutOptions: data.layoutOptions,
      updatedAt: Date.now(),
    }
    localStorage.setItem(getWorksheetPresetKey(noteTypeId), JSON.stringify(payload))
  } catch (err) {
    console.warn('Failed to save worksheet preset for note type:', noteTypeId, err)
  }
}

import type {
  DeckWorksheetMeta,
  WorksheetFieldMapping,
  WorksheetLayoutOptions,
  WorksheetTemplate,
} from '../types'
import { loadWorksheetPreset } from './worksheetStorage'

export const DECK_DEFAULT_TEMPLATE_ID = 'kanji_compact'
export const STANDALONE_DEFAULT_TEMPLATE_ID = 'genkouyoushi'

export function defaultTemplateIdFor(deckId: number | null | undefined): string {
  return deckId ? DECK_DEFAULT_TEMPLATE_ID : STANDALONE_DEFAULT_TEMPLATE_ID
}

/** Worksheets need exactly one note type to map fields reliably. */
export function hasMixedNoteTypes(meta: DeckWorksheetMeta | null | undefined): boolean {
  return Boolean(meta && (meta.has_mixed_note_types || (meta.note_types && meta.note_types.length > 1)))
}

export function buildDefaultFieldMapping(meta: DeckWorksheetMeta): WorksheetFieldMapping {
  const suggested = meta.suggested_mappings
  return {
    kanji: suggested?.kanji || 'Expression',
    reading: suggested?.reading || '',
    meaning: suggested?.meaning || '',
    word: suggested?.word || 'Expression',
    prompt_reading: suggested?.prompt_reading || '',
    prompt_meaning: suggested?.prompt_meaning || 'Meaning',
    sentence: suggested?.sentence || suggested?.kanji || 'Expression',
    grammar_point: suggested?.grammar_point || suggested?.kanji || 'Expression',
    meaning_usage: suggested?.meaning_usage || suggested?.meaning || '',
    example: suggested?.example || suggested?.reading || '',
    custom_columns: [],
  }
}

export interface StudioSetup {
  noteTypeId: string | null
  templateId: string
  template: WorksheetTemplate | undefined
  fieldMapping: WorksheetFieldMapping
  layoutOptions: WorksheetLayoutOptions
}

/**
 * Initial studio state for freshly loaded deck metadata: the note type's saved
 * preset wins, then the template defaults, then the deck's suggested mappings.
 */
export function resolveStudioSetup(
  meta: DeckWorksheetMeta,
  {
    deckId,
    deckName,
    baseOptions,
  }: { deckId: number | null; deckName?: string; baseOptions: WorksheetLayoutOptions },
): StudioSetup {
  const primaryNoteType = meta.note_types?.[0]
  const preset = meta.note_types?.length === 1 ? loadWorksheetPreset(primaryNoteType.id) : null
  const templateId = preset?.templateId || defaultTemplateIdFor(deckId)
  const template = meta.templates?.find((item) => item.id === templateId)
  const presetMapping = preset?.fieldMapping && Object.keys(preset.fieldMapping).length > 0
    ? preset.fieldMapping
    : null

  return {
    noteTypeId: primaryNoteType ? String(primaryNoteType.id) : null,
    templateId,
    template,
    fieldMapping: presetMapping || buildDefaultFieldMapping(meta),
    layoutOptions: {
      ...baseOptions,
      locale: meta.detected_locale || 'ja',
      header_title: templateId === STANDALONE_DEFAULT_TEMPLATE_ID ? '' : (meta.deck_name || deckName || ''),
      ...(template?.default_options || {}),
      ...(preset?.layoutOptions || {}),
    },
  }
}

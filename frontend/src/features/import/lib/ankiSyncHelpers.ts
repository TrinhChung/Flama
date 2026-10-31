import type { AnkiCardInfo } from './ankiConnectClient'
import type { AnkiNoteSyncState, SyncNoteStatus } from './ankiIndexedDB'

export interface ImportCardResult {
  ankiNoteId?: number
  imported?: boolean
  noteId?: string | number | null
  error?: string
}

export const COMMON_MAPPING_RULES: Record<string, string[]> = {
  Word: ['Word', 'Expression', 'Term', 'Front', 'Kanji', 'Vocab'],
  Meaning: ['Meaning', 'Definition', 'Back', 'Translation', 'Glossary'],
  Reading: ['Reading', 'Furigana', 'Kana', 'Pronunciation'],
  Example: ['Example', 'Sentence', 'Context', 'Example Sentence'],
  Audio: ['Audio', 'Sound', 'Pronunciation Audio'],
  Image: ['Image', 'Picture', 'Photo', 'Illustration'],
}

export async function calculateStringHash(text: string): Promise<string> {
  const buffer = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(buffer)).map((value) => value.toString(16).padStart(2, '0')).join('')
}

export async function calculateBinaryHash(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest)).map((value) => value.toString(16).padStart(2, '0')).join('')
}

export function autoSuggestFieldMapping(
  ankiFields: string[],
  flamaFields: Array<{ id: string; name: string }>
): Record<string, string> {
  const mapping: Record<string, string> = {}
  for (const flamaField of flamaFields) {
    const rules = COMMON_MAPPING_RULES[flamaField.name] || [flamaField.name]
    const matched = ankiFields.find((field) =>
      rules.some((rule) => field.toLowerCase() === rule.toLowerCase() || field.toLowerCase().includes(rule.toLowerCase()))
    )
    if (matched) mapping[matched] = flamaField.name
  }
  return mapping
}

export function buildExactAnkiDeckQuery(deckName: string): string {
  return `deck:${JSON.stringify(deckName)}`
}

export function buildExactAnkiModelQuery(deckName: string, modelName: string): string {
  return `${buildExactAnkiDeckQuery(deckName)} note:${JSON.stringify(modelName)}`
}

export function isDeckInSubtree(rootDeck: string, candidate: string): boolean {
  return candidate === rootDeck || candidate.startsWith(`${rootDeck}::`)
}

export function mapAnkiDeckPath(sourceRoot: string, sourcePath: string, targetRoot: string): string {
  if (!isDeckInSubtree(sourceRoot, sourcePath)) {
    throw new Error(`Deck "${sourcePath}" không thuộc cây "${sourceRoot}".`)
  }
  const normalizedTarget = targetRoot.trim() || sourceRoot
  return sourcePath === sourceRoot ? normalizedTarget : `${normalizedTarget}${sourcePath.slice(sourceRoot.length)}`
}

/**
 * A Flama Note lives in one Deck while Anki places each Card separately, so a
 * Note whose Cards were moved apart follows its first Card (lowest ord).
 */
export function indexNoteDecks(cards: AnkiCardInfo[]): Map<number, string> {
  const firstCardByNote = new Map<number, AnkiCardInfo>()
  for (const card of cards) {
    const current = firstCardByNote.get(card.note)
    if (!current || card.ord < current.ord || (card.ord === current.ord && card.cardId < current.cardId)) {
      firstCardByNote.set(card.note, card)
    }
  }
  return new Map([...firstCardByNote].map(([noteId, card]) => [noteId, card.deckName]))
}

export function indexImportCardResults(results: ImportCardResult[] | undefined): Map<number, ImportCardResult> {
  const indexed = new Map<number, ImportCardResult>()
  for (const result of results || []) {
    if (typeof result.ankiNoteId === 'number') indexed.set(result.ankiNoteId, result)
  }
  return indexed
}

export function classifyNoteSyncStatus(
  existing: AnkiNoteSyncState | null,
  profileId: string,
  contentHash: string,
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all'
): SyncNoteStatus {
  if (!existing || existing.syncProfileId !== profileId) return 'New'
  if (existing.syncStatus !== 'Synced') return 'New'
  return existing.contentHash === contentHash && syncMode !== 'resync_all' ? 'Unchanged' : 'Changed'
}

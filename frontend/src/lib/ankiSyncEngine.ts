/**
 * Incremental Sync Engine & Local Sync Database (IndexedDB backed).
 */

import type { FlamaAccountInfo } from '@/lib/flamaConnectClient'
import { flamaConnectClient } from '@/lib/flamaConnectClient'
import { ankiConnectClient } from '@/lib/ankiConnectClient'
import {
  extractAudioReferences,
  extractImageReferences,
  replaceMediaReferences,
  sanitizeAnkiHtml,
} from '@/lib/ankiHtmlSanitizer'

export interface AnkiSyncProfile {
  id: string // e.g. "deckName:noteType:userId"
  flamaUserId: number
  ankiEndpoint: string
  deckName: string
  noteType: string
  mappingJson: Record<string, string> // AnkiField -> FlamaField
  updatedAt: string
}

export type SyncNoteStatus = 'New' | 'Changed' | 'Unchanged' | 'Invalid' | 'Syncing' | 'Synced' | 'Error'

export interface AnkiNoteSyncState {
  ankiNoteId: number
  ankiDeckName: string
  ankiNoteType: string
  flamaCardId?: string | number | null
  contentHash: string
  mediaHash?: string
  lastSyncedAt?: string
  syncStatus: SyncNoteStatus
  lastError?: string
  syncProfileId?: string
}

export interface AnkiMediaSyncState {
  fileName: string
  contentHash: string
  flamaMediaId: string
  mimeType: string
  fileSize: number
  lastSyncedAt: string
}

const DB_NAME = 'FlamaAnkiSyncDB_v1'
const DB_VERSION = 1

function openSyncDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('profiles')) {
        db.createObjectStore('profiles', { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains('noteStates')) {
        db.createObjectStore('noteStates', { keyPath: 'ankiNoteId' })
      }
      if (!db.objectStoreNames.contains('mediaStates')) {
        db.createObjectStore('mediaStates', { keyPath: 'fileName' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

// Compute SHA-256 hex string for object/string
export async function calculateStringHash(text: string): Promise<string> {
  const encoder = new TextEncoder()
  const buffer = await crypto.subtle.digest('SHA-256', encoder.encode(text))
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export async function calculateBinaryHash(buffer: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

export async function saveSyncProfile(profile: AnkiSyncProfile): Promise<void> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('profiles', 'readwrite')
    tx.objectStore('profiles').put(profile)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function getSyncProfile(id: string): Promise<AnkiSyncProfile | null> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('profiles', 'readonly')
    const req = tx.objectStore('profiles').get(id)
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function getNoteSyncState(ankiNoteId: number): Promise<AnkiNoteSyncState | null> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('noteStates', 'readonly')
    const req = tx.objectStore('noteStates').get(ankiNoteId)
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function saveNoteSyncState(state: AnkiNoteSyncState): Promise<void> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('noteStates', 'readwrite')
    tx.objectStore('noteStates').put(state)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function getMediaSyncState(fileName: string): Promise<AnkiMediaSyncState | null> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('mediaStates', 'readonly')
    const req = tx.objectStore('mediaStates').get(fileName)
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function saveMediaSyncState(state: AnkiMediaSyncState): Promise<void> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('mediaStates', 'readwrite')
    tx.objectStore('mediaStates').put(state)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

// Common Anki -> Flama Field Mapping Auto-Suggestions
const COMMON_MAPPING_RULES: Record<string, string[]> = {
  Word: ['Word', 'Expression', 'Term', 'Front', 'Kanji', 'Vocab'],
  Meaning: ['Meaning', 'Definition', 'Back', 'Translation', 'Glossary'],
  Reading: ['Reading', 'Furigana', 'Kana', 'Pronunciation'],
  Example: ['Example', 'Sentence', 'Context', 'Example Sentence'],
  Audio: ['Audio', 'Sound', 'Pronunciation Audio'],
  Image: ['Image', 'Picture', 'Photo', 'Illustration'],
}

export function autoSuggestFieldMapping(
  ankiFields: string[],
  flamaFields: Array<{ id: string; name: string }>
): Record<string, string> {
  const mapping: Record<string, string> = {}

  for (const flamaField of flamaFields) {
    const rules = COMMON_MAPPING_RULES[flamaField.name] || [flamaField.name]
    const matchedAnkiField = ankiFields.find((af) =>
      rules.some((rule) => af.toLowerCase() === rule.toLowerCase() || af.toLowerCase().includes(rule.toLowerCase()))
    )
    if (matchedAnkiField) {
      mapping[matchedAnkiField] = flamaField.name
    }
  }

  return mapping
}

export interface SyncProgressUpdate {
  phase: 'fetching' | 'media' | 'uploading' | 'completed' | 'error'
  totalNotes: number
  processedNotes: number
  totalMedia: number
  processedMedia: number
  currentMessage: string
}

export interface AnkiSyncOptions {
  syncMedia?: boolean // Default false (Bulk Vocab Only - Ultra Fast)
  targetDeckName?: string // Custom target Flama deck name/path (e.g. "Tiếng Nhật::N3")
  targetNoteTypeId?: string
  endpoint?: string
}

export function buildExactAnkiDeckQuery(deckName: string): string {
  return `deck:${JSON.stringify(deckName)}`
}

export function buildExactAnkiModelQuery(deckName: string, modelName: string): string {
  return `${buildExactAnkiDeckQuery(deckName)} note:${JSON.stringify(modelName)}`
}

export interface ImportCardResult {
  ankiNoteId?: number
  imported?: boolean
  noteId?: string | number | null
  error?: string
}

export function indexImportCardResults(results: ImportCardResult[] | undefined): Map<number, ImportCardResult> {
  const indexed = new Map<number, ImportCardResult>()
  for (const result of results || []) {
    if (typeof result.ankiNoteId === 'number') indexed.set(result.ankiNoteId, result)
  }
  return indexed
}

export async function executeAnkiSync(
  deckName: string,
  modelName: string,
  fieldMapping: Record<string, string>, // AnkiField -> FlamaField
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all',
  flamaConnectKey: string,
  accountInfo: FlamaAccountInfo,
  onProgress?: (progress: SyncProgressUpdate) => void,
  options: AnkiSyncOptions = {}
): Promise<{ success: boolean; totalSynced: number; totalMediaDetected: number; errors: string[] }> {
  const syncMedia = options.syncMedia ?? false
  const destDeckName = (options.targetDeckName && options.targetDeckName.trim()) || deckName
  const targetNoteTypeId = (options.targetNoteTypeId || '').trim()
  const errors: string[] = []
  if (!targetNoteTypeId) {
    throw new Error('Vui lòng chọn Flama NoteType đích.')
  }
  const syncProfileId = JSON.stringify([
    accountInfo.userId,
    options.endpoint || '',
    deckName,
    modelName,
    destDeckName,
    targetNoteTypeId,
  ])

  // 1. Fetch note IDs for selected deck
  onProgress?.({
    phase: 'fetching',
    totalNotes: 0,
    processedNotes: 0,
    totalMedia: 0,
    processedMedia: 0,
    currentMessage: `Đang lấy danh sách thẻ từ deck ${deckName}...`,
  })

  const noteIds = await ankiConnectClient.findNotes(buildExactAnkiModelQuery(deckName, modelName), options.endpoint)
  if (!noteIds || noteIds.length === 0) {
    return { success: true, totalSynced: 0, totalMediaDetected: 0, errors: [] }
  }

  // Fetch full note information
  const notesInfo = await ankiConnectClient.notesInfo(noteIds, options.endpoint)

  // Filter notes based on note type & calculate content hashes
  const eligibleNotes: Array<{
    info: (typeof notesInfo)[0]
    contentHash: string
    status: SyncNoteStatus
    mappedFields: Record<string, string>
    images: string[]
    audios: string[]
  }> = []

  let totalMediaCount = 0
  const allMediaMap: Record<string, { mediaId: string; url: string }> = {}

  for (let i = 0; i < notesInfo.length; i++) {
    const note = notesInfo[i]
    if (note.modelName !== modelName) continue

    const mappedFields: Record<string, string> = {}
    let combinedText = [
      `user=${accountInfo.userId}`,
      `endpoint=${options.endpoint || ''}`,
      `sourceDeck=${deckName}`,
      `sourceModel=${modelName}`,
      `targetDeck=${destDeckName}`,
      `targetNoteType=${targetNoteTypeId}`,
    ].join('::')

    for (const [ankiFieldName, fieldData] of Object.entries(note.fields)) {
      const flamaFieldName = fieldMapping[ankiFieldName]
      if (flamaFieldName && flamaFieldName !== 'ignore') {
        const rawValue = fieldData.value || ''
        const cleanValue = sanitizeAnkiHtml(rawValue)
        mappedFields[flamaFieldName] = cleanValue
        combinedText += `::${flamaFieldName}=${cleanValue}`
      }
    }

    const contentHash = await calculateStringHash(combinedText)
    const existingState = await getNoteSyncState(note.noteId)

    let status: SyncNoteStatus = 'New'
    if (existingState && existingState.syncProfileId === syncProfileId) {
      if (existingState.contentHash === contentHash && syncMode !== 'resync_all') {
        status = 'Unchanged'
      } else {
        status = 'Changed'
      }
    }

    if (syncMode === 'only_new' && status !== 'New') {
      continue
    }
    if (syncMode === 'new_and_changed' && status === 'Unchanged') {
      continue
    }

    // Extract media references
    const images: string[] = []
    const audios: string[] = []

    for (const fieldValue of Object.values(mappedFields)) {
      extractImageReferences(fieldValue).forEach((img) => {
        if (!images.includes(img)) images.push(img)
      })
      extractAudioReferences(fieldValue).forEach((aud) => {
        if (!audios.includes(aud)) audios.push(aud)
      })
    }

    totalMediaCount += images.length + audios.length

    eligibleNotes.push({
      info: note,
      contentHash,
      status,
      mappedFields,
      images,
      audios,
    })
  }

  let processedMediaCount = 0

  // 2. Fetch & Upload Media via Flama Connect (Only if syncMedia is enabled)
  if (syncMedia && totalMediaCount > 0) {
    onProgress?.({
      phase: 'media',
      totalNotes: eligibleNotes.length,
      processedNotes: 0,
      totalMedia: totalMediaCount,
      processedMedia: 0,
      currentMessage: `Đang xử lý & upload media (${totalMediaCount} file)...`,
    })

    for (const noteItem of eligibleNotes) {
      const allMediaFiles = [...noteItem.images, ...noteItem.audios]
      for (const filename of allMediaFiles) {
        if (allMediaMap[filename]) continue

        // Check local media sync cache by filename
        const cachedMedia = await getMediaSyncState(filename)
        if (cachedMedia) {
          allMediaMap[filename] = { mediaId: cachedMedia.flamaMediaId, url: `${flamaConnectClient['baseUrl']}/media/${cachedMedia.flamaMediaId}` }
          continue
        }

        // Retrieve binary file from AnkiConnect
        const base64Data = await ankiConnectClient.retrieveMediaFile(filename, options.endpoint)
        if (!base64Data) {
          errors.push(`Không thể đọc file media "${filename}" từ AnkiDesktop.`)
          continue
        }

        try {
          const byteCharacters = atob(base64Data)
          const byteNumbers = new Array(byteCharacters.length)
          for (let j = 0; j < byteCharacters.length; j++) {
            byteNumbers[j] = byteCharacters.charCodeAt(j)
          }
          const byteArray = new Uint8Array(byteNumbers)
          const fileBlob = new Blob([byteArray], { type: filename.endsWith('.mp3') ? 'audio/mpeg' : 'image/png' })
          const fileObj = new File([fileBlob], filename, { type: fileBlob.type })

          const uploadRes = await flamaConnectClient.uploadMediaAsync(fileObj, flamaConnectKey)
          allMediaMap[filename] = { mediaId: uploadRes.mediaId, url: uploadRes.url }

          await saveMediaSyncState({
            fileName: filename,
            contentHash: uploadRes.contentHash,
            flamaMediaId: uploadRes.mediaId,
            mimeType: uploadRes.mimeType,
            fileSize: uploadRes.size,
            lastSyncedAt: new Date().toISOString(),
          })

          processedMediaCount++
          onProgress?.({
            phase: 'media',
            totalNotes: eligibleNotes.length,
            processedNotes: 0,
            totalMedia: totalMediaCount,
            processedMedia: processedMediaCount,
            currentMessage: `Đã upload media ${filename}...`,
          })
        } catch (err: any) {
          errors.push(`Lỗi upload media ${filename}: ${err?.message || err}`)
        }
      }
    }
  }

  // 3. Create Flama Import Session
  const importSession = await flamaConnectClient.createImportSessionAsync(
    {
      source: 'AnkiDesktop',
      selectedDecks: [destDeckName],
      totalNotes: eligibleNotes.length,
      totalMedia: totalMediaCount,
    },
    flamaConnectKey
  )

  // 4. Batch Import Cards to Flama (Higher BATCH_SIZE 50 for Bulk Vocab Sync)
  const BATCH_SIZE = syncMedia ? 20 : 50
  let syncedNotesCount = 0

  for (let i = 0; i < eligibleNotes.length; i += BATCH_SIZE) {
    const batch = eligibleNotes.slice(i, i + BATCH_SIZE)

    const payloadCards = batch.map((item) => {
      // Replace media references in fields if media map exists
      const finalFields: Record<string, string> = {}
      for (const [k, v] of Object.entries(item.mappedFields)) {
        finalFields[k] = Object.keys(allMediaMap).length > 0 ? replaceMediaReferences(v, allMediaMap) : v
      }

      return {
        ankiNoteId: item.info.noteId,
        contentHash: item.contentHash,
        note: {
          deckName: destDeckName,
          modelName: targetNoteTypeId,
          fields: finalFields,
          tags: item.info.tags,
        },
      }
    })

    try {
      const importResult = await flamaConnectClient.importCardsAsync(
        {
          importSessionId: importSession.importSessionId,
          cards: payloadCards,
          deckName: destDeckName,
        },
        flamaConnectKey
      )

      const resultByNoteId = indexImportCardResults(importResult.results)

      for (const item of batch) {
        const cardResult = resultByNoteId.get(item.info.noteId)
        const imported = cardResult?.imported === true
        const errorMessage = cardResult?.error || 'Máy chủ không trả kết quả cho thẻ này.'
        await saveNoteSyncState({
          ankiNoteId: item.info.noteId,
          ankiDeckName: deckName,
          ankiNoteType: modelName,
          flamaCardId: imported ? cardResult?.noteId : null,
          contentHash: item.contentHash,
          lastSyncedAt: new Date().toISOString(),
          syncStatus: imported ? 'Synced' : 'Error',
          lastError: imported ? undefined : errorMessage,
          syncProfileId,
        })
        if (imported) {
          syncedNotesCount++
        } else {
          errors.push(`Thẻ Anki #${item.info.noteId}: ${errorMessage}`)
        }
      }

      onProgress?.({
        phase: 'uploading',
        totalNotes: eligibleNotes.length,
        processedNotes: syncedNotesCount,
        totalMedia: totalMediaCount,
        processedMedia: processedMediaCount,
        currentMessage: `Bulk đồng bộ từ vựng (${syncedNotesCount}/${eligibleNotes.length} thẻ)...`,
      })
    } catch (err: any) {
      errors.push(`Lỗi nạp batch thẻ: ${err?.message || err}`)
    }
  }

  onProgress?.({
    phase: 'completed',
    totalNotes: eligibleNotes.length,
    processedNotes: syncedNotesCount,
    totalMedia: totalMediaCount,
    processedMedia: processedMediaCount,
    currentMessage: `Đã hoàn tất đồng bộ bulk ${syncedNotesCount} thẻ từ vựng!`,
  })

  return { success: errors.length === 0, totalSynced: syncedNotesCount, totalMediaDetected: totalMediaCount, errors }
}

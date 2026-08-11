/**
 * Anki -> Flama sync planner and incremental state.
 *
 * The selected Anki deck is a subtree. Card metadata is the source of truth
 * for deck placement; a single destination deck must never flatten children.
 */

import type { AnkiImportNoteTypePlan } from '@/features/import/api'
import { ankiImportApi } from '@/features/import/api'
import type { AnkiCardInfo, AnkiNoteInfo } from '@/lib/ankiConnectClient'
import { ankiConnectClient } from '@/lib/ankiConnectClient'
import {
  buildCardNdjsonPackage,
  buildMediaZip,
  detectMediaType,
  shouldFlushMediaPackage,
  type MediaPackageEntry,
  uploadPackageWithRetry,
} from '@/lib/ankiSyncPackages'
import {
  extractAudioReferences,
  extractImageReferences,
  sanitizeAnkiHtml,
} from '@/lib/ankiHtmlSanitizer'

import {
  openSyncDB,
  saveSyncProfile,
  getSyncProfile,
  getNoteSyncState,
  saveNoteSyncState,
  DB_NAME,
  DB_VERSION,
} from './ankiIndexedDB'
export {
  openSyncDB,
  saveSyncProfile,
  getSyncProfile,
  getNoteSyncState,
  saveNoteSyncState,
  DB_NAME,
  DB_VERSION,
}
export type {
  AnkiSyncProfile,
  SyncNoteStatus,
  AnkiNoteSyncState,
  AnkiMediaSyncState,
} from './ankiIndexedDB'

import {
  calculateStringHash,
  calculateBinaryHash,
  autoSuggestFieldMapping,
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
  isDeckInSubtree,
  mapAnkiDeckPath,
  indexCardDecksByNote,
  indexImportCardResults,
  classifyNoteSyncStatus,
  COMMON_MAPPING_RULES,
} from './ankiSyncHelpers'
export {
  calculateStringHash,
  calculateBinaryHash,
  autoSuggestFieldMapping,
  buildExactAnkiDeckQuery,
  buildExactAnkiModelQuery,
  isDeckInSubtree,
  mapAnkiDeckPath,
  indexCardDecksByNote,
  indexImportCardResults,
  classifyNoteSyncStatus,
  COMMON_MAPPING_RULES,
}
export type { ImportCardResult } from './ankiSyncHelpers'

export interface SyncTargetNoteType {
  id: string
  name: string
  fields: Array<{ id: string; name: string; field_type: string }>
}

export interface SyncProgressUpdate {
  phase: 'fetching' | 'preflight' | 'media' | 'uploading' | 'completed' | 'error'
  totalNotes: number
  processedNotes: number
  totalMedia: number
  processedMedia: number
  currentMessage: string
}

export interface AnkiSyncOptions {
  syncMedia?: boolean
  targetDeckName?: string
  targetNoteTypeId?: string
  endpoint?: string
  noteTypeOptions?: SyncTargetNoteType[]
  autoSyncMissingNoteTypes?: boolean
  noteTypeMap?: Record<string, string>
}

const ANKI_CARD_BATCH_SIZE = 500
const ANKI_NOTE_BATCH_SIZE = 250

function inferAnkiFieldType(name: string): string {
  const lower = name.toLowerCase()
  if (/(audio|sound|voice)/.test(lower)) return 'audio'
  if (/(image|picture|photo|\bimg\b)/.test(lower)) return 'image'
  if (/(meaning|definition|example|back|content)/.test(lower)) return 'richtext'
  return 'text'
}

function chunks<T>(values: T[], size: number): T[][] {
  const result: T[][] = []
  for (let index = 0; index < values.length; index += size) result.push(values.slice(index, index + size))
  return result
}

async function fetchCardsInfo(cardIds: number[], endpoint?: string): Promise<AnkiCardInfo[]> {
  const result: AnkiCardInfo[] = []
  for (const batch of chunks(cardIds, ANKI_CARD_BATCH_SIZE)) {
    result.push(...(await ankiConnectClient.cardsInfo(batch, endpoint)))
  }
  return result
}

async function fetchNotesInfo(noteIds: number[], endpoint?: string): Promise<AnkiNoteInfo[]> {
  const result: AnkiNoteInfo[] = []
  for (const batch of chunks(noteIds, ANKI_NOTE_BATCH_SIZE)) {
    result.push(...(await ankiConnectClient.notesInfo(batch, endpoint)))
  }
  return result
}

function savedTargetId(modelName: string, noteTypeMap?: Record<string, string>): string {
  if (noteTypeMap && modelName in noteTypeMap) {
    return noteTypeMap[modelName]
  }
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      const raw = localStorage.getItem(`anki_nt_map_${modelName}`)
      if (!raw) return ''
      return String(JSON.parse(raw)?.flamaNoteTypeId || '')
    } catch {
      return ''
    }
  }
  return ''
}

function normalizeMediaFieldValue(value: string, targetFieldType: string): string {
  if (targetFieldType === 'audio') {
    const filename = extractAudioReferences(value)[0]
    return filename ? `[sound:${filename}]` : value.trim()
  }
  if (targetFieldType === 'image' || targetFieldType === 'diagram') {
    return extractImageReferences(value)[0] || value.trim()
  }
  return sanitizeAnkiHtml(value)
}

function mediaReferencesForValue(value: string, fieldType: string): { images: string[]; audios: string[] } {
  if (fieldType === 'audio') {
    const audios = extractAudioReferences(value)
    const direct = value.replace(/^\[sound:|\]$/g, '').trim()
    return { images: [], audios: audios.length > 0 ? audios : direct ? [direct] : [] }
  }
  if (fieldType === 'image' || fieldType === 'diagram') {
    const images = extractImageReferences(value)
    return { images: images.length > 0 ? images : value.trim() ? [value.trim()] : [], audios: [] }
  }
  return { images: extractImageReferences(value), audios: extractAudioReferences(value) }
}

export async function executeAnkiSync(
  deckName: string,
  modelName: string,
  fieldMapping: Record<string, string>,
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all',
  flamaUserId: number,
  onProgress?: (progress: SyncProgressUpdate) => void,
  options: AnkiSyncOptions = {}
): Promise<{ success: boolean; totalSynced: number; totalMediaDetected: number; errors: string[] }> {
  const endpoint = options.endpoint || ''
  const syncMedia = options.syncMedia !== false
  const targetRoot = options.targetDeckName?.trim() || deckName
  const sourceKey = JSON.stringify([flamaUserId, endpoint || 'default-anki'])
  const errors: string[] = []

  onProgress?.({
    phase: 'fetching', totalNotes: 0, processedNotes: 0, totalMedia: 0, processedMedia: 0,
    currentMessage: `Đang quét cây deck ${deckName}...`,
  })

  const [deckNamesAndIds, modelNamesAndIds, cardIds] = await Promise.all([
    ankiConnectClient.getDeckNamesAndIds(endpoint),
    ankiConnectClient.getModelNamesAndIds(endpoint),
    ankiConnectClient.findCards(buildExactAnkiDeckQuery(deckName), endpoint),
  ])
  const cardsInfo = await fetchCardsInfo(cardIds, endpoint)
  const deckSetsByNote = indexCardDecksByNote(cardsInfo)
  const ambiguous = [...deckSetsByNote.entries()].filter(([, decks]) => decks.size !== 1)
  if (ambiguous.length > 0) {
    const examples = ambiguous.slice(0, 5).map(([noteId, decks]) => `#${noteId}: ${[...decks].join(', ')}`)
    throw new Error(`Có ${ambiguous.length} note có card nằm ở nhiều deck; Flama chưa thể giữ chính xác: ${examples.join('; ')}`)
  }

  const noteIds = [...deckSetsByNote.keys()]
  if (noteIds.length === 0) return { success: true, totalSynced: 0, totalMediaDetected: 0, errors: [] }
  const notesInfo = await fetchNotesInfo(noteIds, endpoint)
  const usedModelNames = [...new Set(notesInfo.map((note) => note.modelName))]
  const targetOptions = options.noteTypeOptions || []

  const plans: AnkiImportNoteTypePlan[] = await Promise.all(
    usedModelNames.map(async (sourceModelName) => {
      const [fields, styling, templates] = await Promise.all([
        ankiConnectClient.getModelFieldNames(sourceModelName, endpoint),
        ankiConnectClient.getModelStyling(sourceModelName, endpoint),
        ankiConnectClient.getModelTemplates(sourceModelName, endpoint),
      ])
      const overrideId = sourceModelName === modelName ? options.targetNoteTypeId || '' : ''
      const persistedId = savedTargetId(sourceModelName, options.noteTypeMap)
      const exactTarget = targetOptions.find((item) => item.name.toLowerCase() === sourceModelName.toLowerCase())
      const target = targetOptions.find((item) => item.id === (overrideId || persistedId)) || exactTarget
      const mapping = sourceModelName === modelName && target?.id === options.targetNoteTypeId
        ? fieldMapping
        : target
          ? autoSuggestFieldMapping(fields, target.fields)
          : Object.fromEntries(fields.map((field) => [field, field]))
      return {
        sourceModelId: String(modelNamesAndIds[sourceModelName] || sourceModelName),
        sourceModelName,
        targetNoteTypeId: target?.id,
        fields: fields.map((name) => ({ name, fieldType: inferAnkiFieldType(name) })),
        templates: templates.map((template) => ({
          name: template.name,
          frontHtml: template.front,
          backHtml: template.back,
          sharedCss: styling.css || '',
        })),
        fieldMapping: mapping,
      }
    })
  )

  const sourceDeckPaths = [...new Set([
    ...Object.keys(deckNamesAndIds).filter((path) => isDeckInSubtree(deckName, path)),
    ...cardsInfo.map((card) => card.deckName),
  ])].sort((left, right) => left.localeCompare(right))
  const targetDeckPaths = sourceDeckPaths.map((path) => mapAnkiDeckPath(deckName, path, targetRoot))
  const deckManifest = sourceDeckPaths.map((sourcePath) => ({
    sourceDeckId: String(deckNamesAndIds[sourcePath] || sourcePath),
    sourcePath,
    targetPath: mapAnkiDeckPath(deckName, sourcePath, targetRoot),
  }))
  const planHash = await calculateStringHash(JSON.stringify({ sourceKey, deckName, targetRoot, sourceDeckPaths, plans }))

  const targetById = new Map(targetOptions.map((item) => [item.id, item]))
  const modelPlanByName = new Map(plans.map((plan) => [plan.sourceModelName, plan]))
  const candidateNotes: Array<{
    info: AnkiNoteInfo
    sourceDeckPath: string
    sourceDeckId: string
    mappedFields: Record<string, string>
    images: string[]
    audios: string[]
  }> = []
  const uniqueMedia = new Set<string>()

  for (const note of notesInfo) {
    const sourceDeckPath = [...(deckSetsByNote.get(note.noteId) || [])][0]
    if (!sourceDeckPath) continue
    const plan = modelPlanByName.get(note.modelName)
    if (!plan) continue
    const target = plan.targetNoteTypeId ? targetById.get(plan.targetNoteTypeId) : undefined
    const targetFieldType = new Map((target?.fields || []).map((field) => [field.name, field.field_type]))
    const mappedFields: Record<string, string> = {}
    const images: string[] = []
    const audios: string[] = []
    for (const [sourceName, field] of Object.entries(note.fields)) {
      const targetName = plan.fieldMapping[sourceName]
      if (!targetName || targetName === 'ignore') continue
      const fieldType = targetFieldType.get(targetName) || inferAnkiFieldType(targetName)
      const normalized = normalizeMediaFieldValue(field.value || '', fieldType)
      mappedFields[targetName] = normalized
      const refs = mediaReferencesForValue(normalized, fieldType)
      images.push(...refs.images)
      audios.push(...refs.audios)
    }
    for (const filename of [...images, ...audios]) uniqueMedia.add(filename)
    candidateNotes.push({
      info: note,
      sourceDeckPath,
      sourceDeckId: String(deckNamesAndIds[sourceDeckPath] || sourceDeckPath),
      mappedFields,
      images: [...new Set(images)],
      audios: [...new Set(audios)],
    })
  }

  onProgress?.({
    phase: 'preflight', totalNotes: candidateNotes.length, processedNotes: 0,
    totalMedia: uniqueMedia.size, processedMedia: 0,
    currentMessage: `Đang kiểm tra ${plans.length} NoteType trước khi đồng bộ...`,
  })
  const session = await ankiImportApi.createSession(
    {
      source: 'anki', sourceKey, sourceRootPath: deckName, targetRootPath: targetRoot,
      selectedDecks: targetDeckPaths, decks: deckManifest, totalNotes: candidateNotes.length,
      totalMedia: syncMedia ? uniqueMedia.size : 0, appVersion: '2.0.0',
      mode: options.autoSyncMissingNoteTypes ? 'auto_sync_missing' : 'strict',
      noteTypes: plans, planHash,
    },
  )
  if (session.status !== 'note_types_ready') {
    const detail = session.blockers.map((item) => `${item.sourceModelName}: ${item.message}`).join('; ')
    throw new Error(`Không thể đồng bộ vì NoteType chưa sẵn sàng. ${detail}`)
  }

  const bindingByModelName = new Map(
    Object.entries(session.noteTypeBindings).map(([sourceModelId, binding]) => [binding.sourceModelName, { sourceModelId, ...binding }])
  )
  const eligible: Array<{
    item: (typeof candidateNotes)[number]
    contentHash: string
    targetDeckPath: string
    targetNoteTypeId: string
    sourceModelId: string
    mappedFields: Record<string, string>
  }> = []
  for (const item of candidateNotes) {
    const binding = bindingByModelName.get(item.info.modelName)
    if (!binding) continue
    const mappedFields: Record<string, string> = {}
    for (const [sourceName, field] of Object.entries(item.info.fields)) {
      const targetName = binding.fieldMapping[sourceName]
      if (!targetName || targetName === 'ignore') continue
      const target = targetById.get(binding.targetNoteTypeId)
      const fieldType = target?.fields.find((fieldDef) => fieldDef.name === targetName)?.field_type || inferAnkiFieldType(targetName)
      mappedFields[targetName] = normalizeMediaFieldValue(field.value || '', fieldType)
    }
    const targetDeckPath = mapAnkiDeckPath(deckName, item.sourceDeckPath, targetRoot)
    const profileId = JSON.stringify([sourceKey, deckName, item.info.modelName, targetDeckPath, binding.targetNoteTypeId])
    const contentHash = await calculateStringHash(JSON.stringify({ profileId, fields: mappedFields, tags: item.info.tags }))
    const existing = await getNoteSyncState(sourceKey, item.info.noteId)
    const status = classifyNoteSyncStatus(existing, profileId, contentHash, syncMode)
    if (syncMode === 'only_new' && status !== 'New') continue
    if (syncMode === 'new_and_changed' && status === 'Unchanged') continue
    eligible.push({ item, contentHash, targetDeckPath, targetNoteTypeId: binding.targetNoteTypeId, sourceModelId: binding.sourceModelId, mappedFields })
  }

  let processedMedia = 0
  const mediaRename = new Map<string, string>()
  if (syncMedia) {
    const capabilities = await ankiImportApi.capabilities()
    let packageEntries: MediaPackageEntry[] = []
    let packageRenames: Array<[string, string]> = []
    let packageSafeNames = new Set<string>()
    const uploadedSafeNames = new Set<string>()
    let packageBytes = 0
    let packageSequence = 0

    const flushPackage = async () => {
      if (packageEntries.length === 0) return
      const entries = [...packageEntries]
      const renames = [...packageRenames]
      try {
        const zipBlob = await buildMediaZip(entries)
        if (zipBlob.size > capabilities.mediaPackageMaxBytes) {
          throw new Error(`Package media ${packageSequence} vượt giới hạn ${capabilities.mediaPackageMaxBytes} byte.`)
        }
        const packageHash = await calculateBinaryHash(await zipBlob.arrayBuffer())
        await uploadPackageWithRetry(
          () => ankiImportApi.uploadMediaPackage(
              session.importSessionId,
              packageSequence,
              zipBlob,
              packageHash,
            ),
          (delayMs) => new Promise((resolve) => window.setTimeout(resolve, delayMs))
        )
        for (const entry of entries) uploadedSafeNames.add(entry.filename)
        for (const [original, safe] of renames) mediaRename.set(original, safe)
      } catch (uploadError: any) {
        errors.push(`Lỗi upload package media ${packageSequence}: ${uploadError?.message || String(uploadError)}`)
      } finally {
        packageEntries = []
        packageRenames = []
        packageSafeNames = new Set<string>()
        packageBytes = 0
        packageSequence++
        processedMedia = mediaRename.size
        onProgress?.({
          phase: 'media', totalNotes: eligible.length, processedNotes: 0,
          totalMedia: uniqueMedia.size, processedMedia,
          currentMessage: `Đã upload package media ${packageSequence} (${processedMedia}/${uniqueMedia.size} file)`,
        })
      }
    }

    for (const filename of uniqueMedia) {
      try {
        const base64 = await ankiConnectClient.retrieveMediaFile(filename, endpoint)
        if (!base64) {
          throw new Error(`Không đọc được từ Anki.`)
        }
        const prepared = await (async () => {
          try {
            const binary = atob(base64)
            const bytes = new Uint8Array(binary.length)
            for (let index = 0; index < binary.length; index++) bytes[index] = binary.charCodeAt(index)
            const mediaType = detectMediaType(bytes, filename)
            const mediaHash = await calculateBinaryHash(bytes.buffer)
            const safeFilename = `${mediaHash}.${mediaType.extension}`
            const mediaBlob = new Blob([bytes], { type: mediaType.mimeType })
            return { safeFilename, mediaBlob }
          } catch (error) {
            throw new Error(`Lỗi xử lý file: ${error instanceof Error ? error.message : String(error)}`)
          }
        })()
        const { safeFilename, mediaBlob } = prepared
        if (mediaBlob.size > capabilities.mediaFileMaxBytes) {
          throw new Error(`Vượt giới hạn kích thước file (${capabilities.mediaFileMaxBytes} byte).`)
        }
        if (uploadedSafeNames.has(safeFilename)) {
          mediaRename.set(filename, safeFilename)
          processedMedia = mediaRename.size
          continue
        }
        if (shouldFlushMediaPackage(
          packageBytes,
          packageEntries.length,
          mediaBlob.size,
          capabilities.mediaPackageMaxBytes,
          capabilities.mediaPackageMaxEntries
        )) {
          await flushPackage()
        }
        if (uploadedSafeNames.has(safeFilename)) {
          mediaRename.set(filename, safeFilename)
          processedMedia = mediaRename.size
          continue
        }
        if (!packageSafeNames.has(safeFilename)) {
          packageEntries.push({ filename: safeFilename, blob: mediaBlob })
          packageBytes += mediaBlob.size
          packageSafeNames.add(safeFilename)
        }
        packageRenames.push([filename, safeFilename])
      } catch (mediaError: any) {
        errors.push(`Lỗi media "${filename}": ${mediaError?.message || String(mediaError)}`)
      }
    }
    await flushPackage()
    for (const entry of eligible) {
      for (const [fieldName, value] of Object.entries(entry.mappedFields)) {
        let updated = value
        for (const [original, safe] of mediaRename) {
          if (updated === original) updated = safe
          if (updated === `[sound:${original}]`) updated = `[sound:${safe}]`
        }
        entry.mappedFields[fieldName] = updated
      }
    }
  }

  let totalSynced = 0
  let cardPackageSequence = 0
  for (const batch of chunks(eligible, 50)) {
    const cards = batch.map(({ item, contentHash, targetDeckPath, targetNoteTypeId, sourceModelId, mappedFields }) => ({
      ankiNoteId: item.info.noteId,
      sourceModelId,
      sourceDeckId: item.sourceDeckId,
      sourceDeckPath: item.sourceDeckPath,
      contentHash,
      note: { deckName: targetDeckPath, modelName: targetNoteTypeId, fields: mappedFields, tags: item.info.tags },
    }))
    try {
      const cardPackage = await buildCardNdjsonPackage(cards)
      const cardPackageHash = await calculateBinaryHash(await cardPackage.blob.arrayBuffer())
      const result = await uploadPackageWithRetry(
        () => ankiImportApi.uploadCardPackage(
            session.importSessionId,
            cardPackageSequence,
            cardPackage.blob,
            cardPackageHash,
            cardPackage.contentEncoding,
          ),
        (delayMs) => new Promise((resolve) => window.setTimeout(resolve, delayMs))
      )
      cardPackageSequence++
      const byNote = indexImportCardResults(result.results)
      for (const entry of batch) {
        const outcome = byNote.get(entry.item.info.noteId)
        const imported = outcome?.imported === true
        const profileId = JSON.stringify([sourceKey, deckName, entry.item.info.modelName, entry.targetDeckPath, entry.targetNoteTypeId])
        await saveNoteSyncState({
          sourceKey, ankiNoteId: entry.item.info.noteId, ankiDeckName: entry.item.sourceDeckPath,
          ankiNoteType: entry.item.info.modelName, flamaCardId: imported ? outcome?.noteId : null,
          contentHash: entry.contentHash, lastSyncedAt: new Date().toISOString(),
          syncStatus: imported ? 'Synced' : 'Error', lastError: imported ? undefined : outcome?.error,
          syncProfileId: profileId,
        })
        if (imported) totalSynced++
        else errors.push(`Note Anki #${entry.item.info.noteId}: ${outcome?.error || 'Máy chủ không trả kết quả.'}`)
      }
    } catch (error) {
      errors.push(`Lỗi nhập batch: ${error instanceof Error ? error.message : String(error)}`)
    }
    onProgress?.({
      phase: 'uploading', totalNotes: eligible.length, processedNotes: totalSynced,
      totalMedia: uniqueMedia.size, processedMedia,
      currentMessage: `Đã đồng bộ ${totalSynced}/${eligible.length} note...`,
    })
  }

  await ankiImportApi.completeSession(session.importSessionId)

  onProgress?.({
    phase: 'completed', totalNotes: eligible.length, processedNotes: totalSynced,
    totalMedia: uniqueMedia.size, processedMedia,
    currentMessage: `Hoàn tất đồng bộ ${totalSynced} note.`,
  })
  return { success: errors.length === 0, totalSynced, totalMediaDetected: uniqueMedia.size, errors }
}

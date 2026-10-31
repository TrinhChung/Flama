/**
 * Anki -> Flama sync planner and incremental state.
 *
 * The selected Anki deck is a subtree. Card metadata is the source of truth
 * for deck placement (a Note follows its first Card); a single destination
 * deck must never flatten children.
 */

import type { AnkiImportNoteTypePlan } from '../api'
import { ankiImportApi } from '../api'
import type { AnkiCardInfo, AnkiNoteInfo, AnkiReviewLog } from './ankiConnectClient'
import { ankiConnectClient } from './ankiConnectClient'
import {
  buildCardNdjsonPackage,
  buildMediaZip,
  chunkNdjsonItems,
  detectMediaType,
  resolveAcceptedMediaFilenames,
  rewriteMediaFieldValue,
  shouldFlushMediaPackage,
  type MediaPackageEntry,
  uploadPackageWithRetry,
} from './ankiSyncPackages'
import {
  extractAudioReferences,
  extractImageReferences,
  ankiHtmlToPlainText,
  sanitizeAnkiHtml,
} from './ankiHtmlSanitizer'

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
  indexNoteDecks,
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
  indexNoteDecks,
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

const MEDIA_FILENAME_RE = /^[\p{L}\p{N}_][\p{L}\p{N}_.-]{0,254}$/u;
const MEDIA_EXTENSION_RE = /\.(png|jpg|jpeg|gif|webp|svg|mp3|wav|ogg|webm)$/i;

function isValidMediaFilename(filename: string): boolean {
  return MEDIA_FILENAME_RE.test(filename) && MEDIA_EXTENSION_RE.test(filename);
}

function normalizeMediaFieldValue(value: string, targetFieldType: string): string {
  if (targetFieldType === 'text') return ankiHtmlToPlainText(value)
  if (targetFieldType === 'audio') {
    const filename = extractAudioReferences(value)[0]
    if (filename) return `[sound:${filename}]`
    const trimmed = value.trim()
    if (isValidMediaFilename(trimmed)) return `[sound:${trimmed}]`
    return sanitizeAnkiHtml(value)
  }
  if (targetFieldType === 'image' || targetFieldType === 'diagram') {
    const filename = extractImageReferences(value)[0]
    if (filename) return filename
    const trimmed = value.trim()
    if (isValidMediaFilename(trimmed)) return trimmed
    return sanitizeAnkiHtml(value)
  }
  return sanitizeAnkiHtml(value)
}

function mediaReferencesForValue(value: string, fieldType: string): { images: string[]; audios: string[] } {
  if (fieldType === 'audio') {
    const audios = extractAudioReferences(value)
    if (audios.length > 0) return { images: [], audios }
    const direct = value.replace(/^\[sound:|\]$/g, '').trim()
    if (direct && isValidMediaFilename(direct)) {
      return { images: [], audios: [direct] }
    }
    return { images: [], audios: [] }
  }
  if (fieldType === 'image' || fieldType === 'diagram') {
    const images = extractImageReferences(value)
    if (images.length > 0) return { images, audios: [] }
    const direct = value.trim()
    if (direct && isValidMediaFilename(direct)) {
      return { images: [direct], audios: [] }
    }
    return { images: [], audios: [] }
  }
  return { images: extractImageReferences(value), audios: extractAudioReferences(value) }
}

async function findRelativeDue(cardId: number, endpoint?: string): Promise<number> {
  let low = -100000
  let high = 100000
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    const matched = await ankiConnectClient.findCards(`cid:${cardId} prop:due<=${mid}`, endpoint)
    if (matched.length > 0) {
      high = mid - 1
    } else {
      low = mid + 1
    }
  }
  return low
}

export function canonicalizeAnkiEndpoint(endpoint?: string): string {
  const raw = String(endpoint || 'http://127.0.0.1:8765').trim() || 'http://127.0.0.1:8765'
  try {
    const parsed = new URL(raw)
    if (['localhost', '[::1]', '::1'].includes(parsed.hostname)) parsed.hostname = '127.0.0.1'
    parsed.pathname = ''
    parsed.search = ''
    parsed.hash = ''
    return parsed.origin.toLowerCase()
  } catch {
    return raw.replace(/\/+$/, '').toLowerCase()
  }
}

export function ankiProgressSnapshot(card: AnkiCardInfo) {
  return {
    sourceCardId: card.cardId,
    ord: card.ord,
    type: card.type,
    queue: card.queue,
    due: card.due,
    interval: card.interval,
    factor: card.factor,
    reps: card.reps,
    lapses: card.lapses,
    left: card.left || 0,
    mod: card.mod || 0,
  }
}

export function ankiReviewRecord(sourceCardId: number, log: AnkiReviewLog) {
  return {
    sourceReviewId: log.id,
    sourceCardId,
    ease: log.ease,
    type: log.type,
    ivl: log.ivl,
    lastIvl: log.lastIvl,
    factor: log.factor,
    time: log.time,
  }
}

export function attachProgressSnapshotBase<T extends { sourceCardId: number }>(
  record: T,
  serverSnapshotHash: string | null | undefined,
) {
  return {
    ...record,
    baseSnapshotHash: serverSnapshotHash ?? null,
  }
}

export function shouldQueueAnkiHistory(params: {
  reps: number
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all'
  progressState?: 'new' | 'changed' | 'unchanged' | 'local_changed'
  reviewCursor?: string | null
  progressUploadFailed: boolean
  mappedDuringProgress: boolean
}): boolean {
  if (params.reps <= 0 || params.progressUploadFailed) return false
  if (params.progressState === 'new' && !params.mappedDuringProgress) return false
  return (
    params.syncMode === 'resync_all' ||
    !params.reviewCursor ||
    params.progressState === 'new' ||
    params.progressState === 'changed' ||
    params.progressState === 'local_changed'
  )
}

export async function executeAnkiSync(
  deckName: string,
  modelName: string,
  fieldMapping: Record<string, string>,
  syncMode: 'new_and_changed' | 'only_new' | 'resync_all',
  onProgress?: (progress: SyncProgressUpdate) => void,
  options: AnkiSyncOptions = {}
): Promise<{ success: boolean; totalSynced: number; totalSkipped: number; totalMediaDetected: number; errors: string[] }> {
  const endpoint = options.endpoint || ''
  const syncMedia = options.syncMedia !== false
  const targetRoot = options.targetDeckName?.trim() || deckName
  // The profile name follows the collection through AnkiWeb sync; the media
  // folder path in the anki-v2 key differed per machine, so a second computer
  // started a new source and imported every note again. The server moves refs
  // from the v2 alias to this key.
  const sourceKey = `anki-v3:${await calculateStringHash(await ankiConnectClient.getActiveProfile(endpoint))}`
  const sourceAliases = [
    `anki-v2:${await calculateStringHash(await ankiConnectClient.getLegacyCollectionIdentity(endpoint))}`,
  ]
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
  const deckByNote = indexNoteDecks(cardsInfo)

  const noteIds = [...deckByNote.keys()]
  if (noteIds.length === 0) {
    return { success: true, totalSynced: 0, totalSkipped: 0, totalMediaDetected: 0, errors: [] }
  }
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
    const sourceDeckPath = deckByNote.get(note.noteId)
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

  const cardsInfoMap = new Map<number, AnkiCardInfo>(cardsInfo.map((card) => [card.cardId, card]))
  const allCardIds = candidateNotes.flatMap((note) => note.info.cards || [])
  const missingCardIds = allCardIds.filter((id) => !cardsInfoMap.has(id))
  if (missingCardIds.length > 0) {
    const extraCardsInfo = await fetchCardsInfo(missingCardIds, endpoint)
    for (const card of extraCardsInfo) {
      cardsInfoMap.set(card.cardId, card)
    }
  }

  const reviewCard = [...cardsInfoMap.values()].find(
    (card) => card.type === 2 || (card.queue === 3 && (card.type === 1 || card.type === 3)),
  )
  let todayDayIndexAnki: number | null = null
  if (reviewCard) {
    try {
      const relativeDue = await findRelativeDue(reviewCard.cardId, endpoint)
      todayDayIndexAnki = reviewCard.due - relativeDue
    } catch (e) {
      console.warn('Error resolving todayDayIndexAnki:', e)
    }
  }

  onProgress?.({
    phase: 'preflight', totalNotes: candidateNotes.length, processedNotes: 0,
    totalMedia: uniqueMedia.size, processedMedia: 0,
    currentMessage: `Đang kiểm tra ${plans.length} NoteType trước khi đồng bộ...`,
  })
  const session = await ankiImportApi.createSession(
    {
      source: 'anki', sourceKey, sourceAliases, sourceRootPath: deckName, targetRootPath: targetRoot,
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
  type PreparedSyncNote = {
    item: (typeof candidateNotes)[number]
    contentHash: string
    targetDeckPath: string
    targetNoteTypeId: string
    sourceModelId: string
    mappedFields: Record<string, string>
    progressRecords: Array<ReturnType<typeof ankiProgressSnapshot> & {
      externalNoteId: number
      snapshotHash: string
      sourceToday: number | null
      force: boolean
    }>
    knownMediaHashes: Set<string>
  }
  const preparedNotes: PreparedSyncNote[] = []
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
    const profileId = JSON.stringify([deckName, item.info.modelName, targetDeckPath, binding.targetNoteTypeId])
    const progressRecords = (await Promise.all((item.info.cards || []).map(async (cardId) => {
      const card = cardsInfoMap.get(cardId)
      if (!card) return null
      const snapshot = ankiProgressSnapshot(card)
      return {
        ...snapshot,
        externalNoteId: item.info.noteId,
        snapshotHash: await calculateStringHash(JSON.stringify(snapshot)),
        sourceToday: todayDayIndexAnki,
        force: syncMode === 'resync_all',
      }
    }))).filter((record): record is NonNullable<typeof record> => record !== null)
    const contentHash = await calculateStringHash(JSON.stringify({
      profileId,
      fields: mappedFields,
      tags: item.info.tags,
    }))
    preparedNotes.push({
      item,
      contentHash,
      targetDeckPath,
      targetNoteTypeId: binding.targetNoteTypeId,
      sourceModelId: binding.sourceModelId,
      mappedFields,
      progressRecords,
      knownMediaHashes: new Set<string>(),
    })
  }

  const serverStateByNote = new Map<number, {
    state: 'new' | 'changed' | 'unchanged'
    mediaHashes: string[]
    cards: Array<{
      sourceCardId: number
      progressState: 'new' | 'changed' | 'unchanged' | 'local_changed'
      serverSnapshotHash: string | null
      reviewCursor: string | null
    }>
  }>()
  for (const batch of chunks(preparedNotes, 500)) {
    const response = await ankiImportApi.getNoteStatuses(
      session.importSessionId,
      batch.map((entry) => ({
        ankiNoteId: entry.item.info.noteId,
        contentHash: entry.contentHash,
        cards: entry.progressRecords.map((record) => ({
          sourceCardId: record.sourceCardId,
          snapshotHash: record.snapshotHash,
        })),
      })),
    )
    for (const state of response.notes) serverStateByNote.set(state.ankiNoteId, state)
  }

  const eligible = preparedNotes.filter((entry) => {
    const serverState = serverStateByNote.get(entry.item.info.noteId)
    if (!serverState) return true
    entry.knownMediaHashes = new Set(serverState.mediaHashes)
    if (syncMode === 'only_new') return serverState.state === 'new'
    if (syncMode === 'new_and_changed') return serverState.state !== 'unchanged'
    return true
  })
  const schedulerEligibleNotes = preparedNotes.filter((entry) => {
    const state = serverStateByNote.get(entry.item.info.noteId)?.state
    return syncMode !== 'only_new' || state === 'new'
  })
  const progressRecords = schedulerEligibleNotes.flatMap((entry) => {
    const cardStates = new Map(
      (serverStateByNote.get(entry.item.info.noteId)?.cards || [])
        .map((card) => [Number(card.sourceCardId), card] as const),
    )
    return entry.progressRecords.filter((record) => {
      const state = cardStates.get(record.sourceCardId)?.progressState || 'new'
      if (state === 'local_changed' && syncMode !== 'resync_all') return false
      return syncMode === 'resync_all' || state === 'new' || state === 'changed'
    }).map((record) => attachProgressSnapshotBase(
      record,
      cardStates.get(record.sourceCardId)?.serverSnapshotHash,
    ))
  })
  const eligibleMedia = syncMedia
    ? new Set(eligible.flatMap((entry) => [...entry.item.images, ...entry.item.audios]))
    : new Set<string>()
  const mediaConsumers = new Map<string, PreparedSyncNote[]>()
  for (const entry of eligible) {
    for (const filename of new Set([...entry.item.images, ...entry.item.audios])) {
      const consumers = mediaConsumers.get(filename) || []
      consumers.push(entry)
      mediaConsumers.set(filename, consumers)
    }
  }

  let processedMedia = 0
  const mediaRename = new Map<string, string>()
  const capabilities = await ankiImportApi.capabilities()
  if (syncMedia) {
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
        const result = await uploadPackageWithRetry(
          () => ankiImportApi.uploadMediaPackage(
              session.importSessionId,
              packageSequence,
              zipBlob,
              packageHash,
            ),
          (delayMs) => new Promise((resolve) => globalThis.setTimeout(resolve, delayMs))
        )
        const accepted = resolveAcceptedMediaFilenames(
          result.acceptedFilenames,
          result.itemCount,
          entries.map((entry) => entry.filename),
        )
        for (const entry of entries) {
          if (accepted.has(entry.filename)) uploadedSafeNames.add(entry.filename)
        }
        for (const [original, safe] of renames) {
          if (accepted.has(safe)) mediaRename.set(original, safe)
        }
        for (const rejected of result.rejectedFilenames || []) {
          console.warn(`Bỏ qua media không hợp lệ "${rejected}".`)
        }
      } catch (uploadError: any) {
        console.warn(`Bỏ qua package media ${packageSequence}: ${uploadError?.message || String(uploadError)}`)
      } finally {
        packageEntries = []
        packageRenames = []
        packageSafeNames = new Set<string>()
        packageBytes = 0
        packageSequence++
        processedMedia = mediaRename.size
        onProgress?.({
          phase: 'media', totalNotes: eligible.length, processedNotes: 0,
          totalMedia: eligibleMedia.size, processedMedia,
          currentMessage: `Đã upload package media ${packageSequence} (${processedMedia}/${eligibleMedia.size} file)`,
        })
      }
    }

    for (const filename of eligibleMedia) {
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
        const mediaHash = safeFilename.split('.', 1)[0]
        const consumers = mediaConsumers.get(filename) || []
        if (
          consumers.length > 0 &&
          consumers.every((entry) => entry.knownMediaHashes.has(mediaHash))
        ) {
          mediaRename.set(filename, safeFilename)
          processedMedia = mediaRename.size
          continue
        }
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
        console.warn(`Bỏ qua media "${filename}": ${mediaError?.message || String(mediaError)}`)
      }
    }
    await flushPackage()
    for (const entry of eligible) {
      const referencedMedia = new Set([...entry.item.images, ...entry.item.audios])
      for (const [fieldName, value] of Object.entries(entry.mappedFields)) {
        entry.mappedFields[fieldName] = rewriteMediaFieldValue(
          value,
          referencedMedia,
          mediaRename,
        )
      }
    }
  }

  const cardPackageMaxItems = Math.max(1, Math.min(
    capabilities.cardPackageMaxItems || 1_000,
    capabilities.cardPackageTargetItems || capabilities.cardBatchMaxItems || 500,
  ))
  const cardPackageMaxBytes = Math.min(
    capabilities.cardPackageMaxBytes || capabilities.mediaPackageMaxBytes,
    capabilities.cardPackageMaxUncompressedBytes || capabilities.mediaPackageMaxUncompressedBytes,
  )
  const toCardPackageRecord = ({
    item,
    contentHash,
    targetDeckPath,
    targetNoteTypeId,
    sourceModelId,
    mappedFields,
  }: PreparedSyncNote) => ({
    ankiNoteId: item.info.noteId,
    sourceModelId,
    sourceDeckId: item.sourceDeckId,
    sourceDeckPath: item.sourceDeckPath,
    contentHash,
    note: {
      deckName: targetDeckPath,
      modelName: targetNoteTypeId,
      fields: mappedFields,
      tags: item.info.tags,
    },
  })
  let totalSynced = 0
  let cardPackageSequence = 0
  const cardBatches = chunkNdjsonItems(
    eligible,
    toCardPackageRecord,
    cardPackageMaxItems,
    cardPackageMaxBytes,
  )
  for (const batch of cardBatches) {
    const cards = batch.map(toCardPackageRecord)
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
        (delayMs) => new Promise((resolve) => globalThis.setTimeout(resolve, delayMs))
      )
      cardPackageSequence++
      const byNote = indexImportCardResults(result.results)
      for (const entry of batch) {
        const outcome = byNote.get(entry.item.info.noteId)
        const imported = outcome?.imported === true
        const profileId = JSON.stringify([deckName, entry.item.info.modelName, entry.targetDeckPath, entry.targetNoteTypeId])
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
      totalMedia: eligibleMedia.size, processedMedia,
      currentMessage: `Đã đồng bộ ${totalSynced}/${eligible.length} note...`,
    })
  }

  let progressPackageSequence = 0
  const unmappedHistoryCardIds = new Set<number>()
  const mappedDuringProgress = new Set<number>()
  const progressPackageMaxItems = Math.max(1, Math.min(
    capabilities.progressBatchMaxItems || 1_000,
    capabilities.progressPackageTargetItems || 500,
  ))
  for (const batch of chunks(progressRecords, progressPackageMaxItems)) {
    try {
      const syncPackage = await buildCardNdjsonPackage(batch)
      const packageHash = await calculateBinaryHash(await syncPackage.blob.arrayBuffer())
      const result = await uploadPackageWithRetry(
        () => ankiImportApi.uploadSyncPackage(
          session.importSessionId,
          'progress',
          progressPackageSequence,
          syncPackage.blob,
          packageHash,
          syncPackage.contentEncoding,
        ),
        (delayMs) => new Promise((resolve) => globalThis.setTimeout(resolve, delayMs)),
      )
      progressPackageSequence++
      for (const outcome of result.results) {
        const blocked = new Set([
          'failed',
          'due_unresolved',
          'conflict',
          'local_conflict',
          'source_conflict',
        ]).has(outcome.state)
        if (blocked) {
          const sourceCardId = Number(outcome.sourceCardId)
          if (Number.isFinite(sourceCardId)) unmappedHistoryCardIds.add(sourceCardId)
        } else {
          const sourceCardId = Number(outcome.sourceCardId)
          if (Number.isFinite(sourceCardId)) mappedDuringProgress.add(sourceCardId)
        }
        if (blocked) {
          errors.push(`Card Anki #${outcome.sourceCardId}: ${outcome.error || 'Không đồng bộ được tiến độ.'}`)
        }
      }
    } catch (error) {
      for (const record of batch) unmappedHistoryCardIds.add(record.sourceCardId)
      errors.push(`Lỗi đồng bộ tiến độ: ${error instanceof Error ? error.message : String(error)}`)
    }
  }

  try {
    for (const batch of chunks(schedulerEligibleNotes, 500)) {
      const response = await ankiImportApi.getNoteStatuses(
        session.importSessionId,
        batch.map((entry) => ({
          ankiNoteId: entry.item.info.noteId,
          contentHash: entry.contentHash,
          cards: entry.progressRecords.map((record) => ({
            sourceCardId: record.sourceCardId,
            snapshotHash: record.snapshotHash,
          })),
        })),
      )
      for (const state of response.notes) serverStateByNote.set(state.ankiNoteId, state)
    }
  } catch (error) {
    errors.push(`Không thể xác nhận card đã map sau khi đồng bộ progress: ${error instanceof Error ? error.message : String(error)}`)
  }

  const historyCandidates: Array<{ card: AnkiCardInfo; reviewCursor: number }> = []
  for (const entry of schedulerEligibleNotes) {
    const states = new Map(
      (serverStateByNote.get(entry.item.info.noteId)?.cards || [])
        .map((card) => [Number(card.sourceCardId), card] as const),
    )
    for (const record of entry.progressRecords) {
      const card = cardsInfoMap.get(record.sourceCardId)
      const state = states.get(record.sourceCardId)
      if (!card || !shouldQueueAnkiHistory({
        reps: card.reps,
        syncMode,
        progressState: state?.progressState,
        reviewCursor: state?.reviewCursor,
        progressUploadFailed: unmappedHistoryCardIds.has(record.sourceCardId),
        mappedDuringProgress: mappedDuringProgress.has(record.sourceCardId),
      })) continue
      const cursor = Number(state?.reviewCursor || 0)
      historyCandidates.push({ card, reviewCursor: Number.isFinite(cursor) ? cursor : 0 })
    }
  }

  const reviewRecords: ReturnType<typeof ankiReviewRecord>[] = []
  try {
    for (const batch of chunks(historyCandidates, 500)) {
      const response = await ankiConnectClient.getReviewsOfCards(
        batch.map((entry) => entry.card.cardId),
        endpoint,
      )
      for (const entry of batch) {
        for (const log of response[entry.card.cardId] || []) {
          if (log.id > entry.reviewCursor) reviewRecords.push(ankiReviewRecord(entry.card.cardId, log))
        }
      }
    }
  } catch (error) {
    errors.push(`Không đọc đủ lịch sử ôn tập từ Anki: ${error instanceof Error ? error.message : String(error)}`)
  }

  reviewRecords.sort((left, right) => left.sourceReviewId - right.sourceReviewId)
  let reviewPackageSequence = 0
  const blockedReviewCardIds = new Set<number>()
  for (const batch of chunks(reviewRecords, 500)) {
    const uploadBatch = batch.filter((record) => !blockedReviewCardIds.has(record.sourceCardId))
    if (uploadBatch.length === 0) continue
    try {
      const syncPackage = await buildCardNdjsonPackage(uploadBatch)
      const packageHash = await calculateBinaryHash(await syncPackage.blob.arrayBuffer())
      const result = await uploadPackageWithRetry(
        () => ankiImportApi.uploadSyncPackage(
          session.importSessionId,
          'reviews',
          reviewPackageSequence,
          syncPackage.blob,
          packageHash,
          syncPackage.contentEncoding,
        ),
        (delayMs) => new Promise((resolve) => globalThis.setTimeout(resolve, delayMs)),
      )
      reviewPackageSequence++
      for (const outcome of result.results) {
        if (outcome.state === 'failed') {
          const sourceCardId = Number(outcome.sourceCardId)
          if (Number.isFinite(sourceCardId)) blockedReviewCardIds.add(sourceCardId)
          errors.push(`Revlog Anki #${outcome.sourceReviewId}: ${outcome.error || 'Không nhập được lịch sử.'}`)
        }
      }
    } catch (error) {
      errors.push(`Lỗi đồng bộ lịch sử ôn tập: ${error instanceof Error ? error.message : String(error)}`)
      break
    }
  }

  try {
    await ankiImportApi.completeSession(session.importSessionId, eligible.length)
  } catch (error) {
    await ankiImportApi.cancelSession(session.importSessionId).catch(() => undefined)
    errors.push(`Không thể chốt phiên đồng bộ: ${error instanceof Error ? error.message : String(error)}`)
  }

  onProgress?.({
    phase: 'completed', totalNotes: eligible.length, processedNotes: totalSynced,
    totalMedia: eligibleMedia.size, processedMedia,
    currentMessage: `Hoàn tất đồng bộ ${totalSynced} note.`,
  })
  return {
    success: errors.length === 0,
    totalSynced,
    totalSkipped: preparedNotes.length - eligible.length,
    totalMediaDetected: Math.max(0, eligibleMedia.size - processedMedia),
    errors,
  }
}

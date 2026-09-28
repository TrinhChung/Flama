import type { SchedulerCardState } from '../scheduler/types'
import type {
  StudyBatchPayload,
  StudyMediaArtifact,
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'
import {
  normalizePersistedStudySession,
} from './sessionRestore'
import type { StudySessionQuarantine } from './sessionRestore'
import { canonicalDigest } from './canonicalDigest'
import { patchRenderContext } from '../renderer/clientRenderer'

const DB_NAME = 'flama-study'
const DB_VERSION = 2
const STORE_NAME = 'sessions'
const QUARANTINE_STORE_NAME = 'session-quarantine'
const memoryFallback = new Map<string, PersistedStudySession>()
const memoryQuarantine = new Map<string, QuarantinedStudySessionRow>()

export type StudyCommitReason =
  | 'auto_finish'
  | 'manual_exit'
  | 'page_exit'
  | 'rollover'

export type StudySessionUndoItem = {
  card_id: string
  previous_state: SchedulerCardState
}

export type StudySessionAccumulatedStats = {
  total_reviews: number
  total_duration_ms: number
  again_count: number
  hard_count: number
  good_count: number
  easy_count: number
}

export type PersistedStudySession = {
  scope_key: string
  snapshot: StudySessionSnapshot
  events: StudySessionEvent[]
  touched_card_ids: string[]
  undo_history?: StudySessionUndoItem[]
  active_card_id?: string | null
  opened_client_at_ms: number
  session_started_at_ms?: number
  accumulated_stats?: StudySessionAccumulatedStats
  status: 'active' | 'pending_commit'
  commit_id: string | null
  commit_reason: StudyCommitReason | null
  resume_after_commit: boolean
  /** Highest batch sequence allocated for this session, including acknowledged batches. */
  batch_sequence?: number
  /** Highest event sequence allocated after accounting for local undo. */
  event_sequence?: number
  /** Keeps the monotonic clock fence after acknowledged events leave the log. */
  acknowledged_scheduler_offset_ms?: number
  /** Accepted batches waiting for a receipt to be reconciled locally. */
  in_flight_batches?: StudyBatchPayload[]
  updated_at_ms: number
}

type QuarantinedStudySessionRow = {
  scope_key: string
  quarantined_at_ms: number
  resolved_at_ms?: number
  reason: StudySessionQuarantine['reason']
  message: string
  raw_session: unknown
  raw_truncated?: boolean
}

const MAX_QUARANTINE_ROWS = 20
const MAX_QUARANTINE_RAW_CHARS = 256_000

function rememberQuarantine(row: QuarantinedStudySessionRow) {
  if (row.resolved_at_ms !== undefined) {
    memoryQuarantine.delete(row.scope_key)
    return
  }
  if (!memoryQuarantine.has(row.scope_key)) {
    memoryQuarantine.set(row.scope_key, row)
  }
  const staleKeys = [...memoryQuarantine.values()]
    .sort((left, right) => right.quarantined_at_ms - left.quarantined_at_ms)
    .slice(MAX_QUARANTINE_ROWS)
    .map((candidate) => candidate.scope_key)
  for (const staleKey of staleKeys) memoryQuarantine.delete(staleKey)
}

function quarantineEvidence(rawSession: unknown) {
  try {
    const serialized = JSON.stringify(rawSession)
    if (serialized.length <= MAX_QUARANTINE_RAW_CHARS) {
      return { raw_session: rawSession, raw_truncated: false }
    }
  } catch {
    // Fall through to a metadata-only diagnostic record.
  }
  const raw = rawSession && typeof rawSession === 'object'
    ? rawSession as Record<string, unknown>
    : {}
  const snapshot = raw.snapshot && typeof raw.snapshot === 'object'
    ? raw.snapshot as Record<string, unknown>
    : {}
  return {
    raw_session: {
      truncated: true,
      scope_key: typeof raw.scope_key === 'string' ? raw.scope_key : null,
      session_id: typeof snapshot.session_id === 'string' ? snapshot.session_id : null,
      schema_version: typeof snapshot.schema_version === 'string'
        ? snapshot.schema_version
        : null,
      event_count: Array.isArray(raw.events) ? raw.events.length : null,
      in_flight_batch_count: Array.isArray(raw.in_flight_batches)
        ? raw.in_flight_batches.length
        : null,
    },
    raw_truncated: true,
  }
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(new Error('IndexedDB is unavailable.'))
      return
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'scope_key' })
      }
      if (!database.objectStoreNames.contains(QUARANTINE_STORE_NAME)) {
        database.createObjectStore(
          QUARANTINE_STORE_NAME,
          { keyPath: 'scope_key' },
        )
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

function transact<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>,
) {
  return openDatabase().then((database) => new Promise<T>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode)
    const request = operation(transaction.objectStore(STORE_NAME))
    let result: T
    request.onsuccess = () => {
      result = request.result
    }
    request.onerror = () => reject(request.error)
    transaction.oncomplete = () => {
      database.close()
      resolve(result)
    }
    transaction.onabort = () => {
      database.close()
      reject(transaction.error)
    }
  }))
}

export function scopeKey(userId: number, scope: string, scopeId: string) {
  return `user:${userId}:${scope}:${scopeId}`
}

export type LoadedStudySession = {
  session: PersistedStudySession | null
  durable: boolean
  quarantine?: StudySessionQuarantine
}

async function moveSessionToQuarantine(
  key: string,
  rawSession: unknown,
  quarantine: StudySessionQuarantine,
) {
  const quarantinedAtMs = Date.now()
  const evidence = quarantineEvidence(rawSession)
  const row: QuarantinedStudySessionRow = {
    scope_key: key,
    quarantined_at_ms: quarantinedAtMs,
    reason: quarantine.reason,
    message: quarantine.message,
    ...evidence,
  }
  memoryFallback.delete(key)
  rememberQuarantine(row)

  const database = await openDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(
      [STORE_NAME, QUARANTINE_STORE_NAME],
      'readwrite',
    )
    const quarantineStore = transaction.objectStore(QUARANTINE_STORE_NAME)
    const activeStore = transaction.objectStore(STORE_NAME)
    const request = quarantineStore.getAll()
    request.onsuccess = () => {
      const existingRows = (request.result as QuarantinedStudySessionRow[]) ?? []
      const existing = existingRows.find((candidate) => candidate.scope_key === key)
      const retained = existing && existing.resolved_at_ms === undefined
        ? existing
        : row
      quarantineStore.put(retained)
      activeStore.delete(key)

      const boundedRows = [
        ...existingRows.filter((candidate) => candidate.scope_key !== key),
        retained,
      ].sort((left, right) => right.quarantined_at_ms - left.quarantined_at_ms)
      for (const stale of boundedRows.slice(MAX_QUARANTINE_ROWS)) {
        quarantineStore.delete(stale.scope_key)
        memoryQuarantine.delete(stale.scope_key)
      }
    }
    request.onerror = () => transaction.abort()
    transaction.oncomplete = () => {
      database.close()
      resolve()
    }
    transaction.onabort = () => {
      database.close()
      reject(transaction.error)
    }
    transaction.onerror = () => reject(transaction.error)
  })
}

function quarantineResult(row: QuarantinedStudySessionRow): StudySessionQuarantine {
  return { reason: row.reason, message: row.message }
}

async function readStoredSessionRows(key: string) {
  const database = await openDatabase()
  return new Promise<{
    active: unknown | undefined
    quarantine: QuarantinedStudySessionRow | undefined
  }>((resolve, reject) => {
    const transaction = database.transaction(
      [STORE_NAME, QUARANTINE_STORE_NAME],
      'readonly',
    )
    const activeRequest = transaction.objectStore(STORE_NAME).get(key)
    const quarantineRequest = transaction.objectStore(QUARANTINE_STORE_NAME).get(key)
    transaction.oncomplete = () => {
      database.close()
      resolve({
        active: activeRequest.result,
        quarantine: quarantineRequest.result,
      })
    }
    transaction.onabort = () => {
      database.close()
      reject(transaction.error)
    }
    transaction.onerror = () => reject(transaction.error)
  })
}

export async function loadStudySessionWithDurability(
  key: string,
): Promise<LoadedStudySession> {
  try {
    const stored = await readStoredSessionRows(key)
    const row = stored.active
    if (stored.quarantine && stored.quarantine.resolved_at_ms === undefined) {
      memoryFallback.delete(key)
      rememberQuarantine(stored.quarantine)
      if (row) {
        try {
          await moveSessionToQuarantine(
            key,
            row,
            quarantineResult(stored.quarantine),
          )
        } catch {
          // Preserve the durable quarantine marker as the authoritative state.
        }
      }
      return {
        session: null,
        durable: true,
        quarantine: quarantineResult(stored.quarantine),
      }
    }
    const memoryBlocked = memoryQuarantine.get(key)
    if (memoryBlocked) {
      return {
        session: null,
        durable: false,
        quarantine: quarantineResult(memoryBlocked),
      }
    }
    const restored = row ?? memoryFallback.get(key) ?? null
    if (!restored) return { session: null, durable: true }
    const result = normalizePersistedStudySession(restored, key)
    if (result.status === 'quarantine') {
      try {
        await moveSessionToQuarantine(key, restored, result.quarantine)
      } catch {
        // The invalid row is removed from the active in-memory store even if
        // durable quarantine is temporarily unavailable.
      }
      return {
        session: null,
        durable: false,
        quarantine: result.quarantine,
      }
    }
    const normalized = result.session
    memoryFallback.set(key, normalized)
    let durable = Boolean(row)
    if (row && result.migrated) {
      try {
        await transact<IDBValidKey>('readwrite', (store) => store.put(normalized))
      } catch {
        durable = false
      }
    }
    return { session: normalized, durable }
  } catch {
    const blocked = memoryQuarantine.get(key)
    if (blocked) {
      return {
        session: null,
        durable: false,
        quarantine: quarantineResult(blocked),
      }
    }
    const fallback = memoryFallback.get(key) ?? null
    if (!fallback) return { session: null, durable: false }
    const result = normalizePersistedStudySession(fallback, key)
    if (result.status === 'quarantine') {
      memoryFallback.delete(key)
      const quarantinedAtMs = Date.now()
      const evidence = quarantineEvidence(fallback)
      const row: QuarantinedStudySessionRow = {
        scope_key: key,
        quarantined_at_ms: quarantinedAtMs,
        reason: result.quarantine.reason,
        message: result.quarantine.message,
        ...evidence,
      }
      rememberQuarantine(row)
      return {
        session: null,
        durable: false,
        quarantine: result.quarantine,
      }
    }
    memoryFallback.set(key, result.session)
    return {
      session: result.session,
      durable: false,
    }
  }
}

/**
 * Mark a quarantined row as user-resolved without deleting its bounded raw
 * evidence. A subsequent malformed row for the same scope replaces this
 * resolved marker and blocks hydration again.
 */
export async function acknowledgeStudySessionQuarantine(key: string) {
  memoryQuarantine.delete(key)
  try {
    const database = await openDatabase()
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(QUARANTINE_STORE_NAME, 'readwrite')
      const store = transaction.objectStore(QUARANTINE_STORE_NAME)
      const request = store.get(key)
      request.onsuccess = () => {
        const row = request.result as QuarantinedStudySessionRow | undefined
        if (row) store.put({ ...row, resolved_at_ms: Date.now() })
      }
      request.onerror = () => transaction.abort()
      transaction.oncomplete = () => {
        database.close()
        resolve()
      }
      transaction.onabort = () => {
        database.close()
        reject(transaction.error)
      }
      transaction.onerror = () => reject(transaction.error)
    })
  } catch {
    // The in-memory blocker is still cleared for this tab. If durable storage
    // becomes available later, the preserved marker can be acknowledged then.
  }
}

export async function loadStudySession(key: string) {
  return (await loadStudySessionWithDurability(key)).session
}

export async function saveStudySession(session: PersistedStudySession) {
  const result = normalizePersistedStudySession(session, session.scope_key)
  if (result.status === 'quarantine') {
    throw new Error(
      `Refusing to persist an invalid study session: ${result.quarantine.reason}.`,
    )
  }
  const normalized = result.session
  memoryFallback.set(normalized.scope_key, normalized)
  try {
    await transact<IDBValidKey>('readwrite', (store) => store.put(normalized))
    return true
  } catch {
    // In private or quota-constrained contexts the in-memory copy still keeps
    // the current tab functional. The UI can continue and commit normally.
    return false
  }
}

export async function removeStudySession(key: string) {
  memoryFallback.delete(key)
  try {
    await transact<undefined>('readwrite', (store) => store.delete(key))
  } catch {
    // Already removed from the current tab fallback.
  }
}

export async function removeStudySessionIfMatches(
  key: string,
  sessionId: string,
) {
  const current = await loadStudySession(key)
  if (current?.snapshot.session_id !== sessionId) return
  await removeStudySession(key)
}

export async function updateCardFieldValuesInSessions(
  cardId: string,
  newFieldValues: Record<string, string>,
  options?: { noteId?: string | null; media?: StudyMediaArtifact[] },
) {
  try {
    const keys: string[] = []
    try {
      const db = await openDatabase()
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const allKeys = await new Promise<IDBValidKey[]>((resolve, reject) => {
        const req = store.getAllKeys()
        req.onsuccess = () => resolve(req.result)
        req.onerror = () => reject(req.error)
      })
      db.close()
      for (const k of allKeys) {
        if (typeof k === 'string') keys.push(k)
      }
    } catch {}

    for (const key of memoryFallback.keys()) {
      if (!keys.includes(key)) keys.push(key)
    }

    for (const key of keys) {
      const session = await loadStudySession(key)
      if (!session) continue
      let updated = false
      const snapshot = session.snapshot
      for (const card of snapshot.cards) {
        if (card.card_id === cardId || (options?.noteId && card.note_id === options.noteId)) {
          const contentKey = card.content_key
          const template = snapshot.templates[card.template_key]
          const existingContent = snapshot.contents[contentKey]
          if (existingContent) {
            const combinedMedia: StudyMediaArtifact[] = options?.media && options.media.length > 0
              ? [...options.media]
              : [...(existingContent.media || [])]

            const existingProxyUrls = new Set(combinedMedia.map((m) => m.proxy_url))
            for (const [fieldName, val] of Object.entries(newFieldValues)) {
              if (typeof val === 'string') {
                const matches = val.match(/\/media\/proxy\/[A-Za-z0-9][A-Za-z0-9_-]{0,127}/g)
                if (matches) {
                  for (const pUrl of matches) {
                    if (!existingProxyUrls.has(pUrl)) {
                      const assetId = pUrl.replace('/media/proxy/', '')
                      const lk = fieldName.toLowerCase()
                      const isAudio = lk.includes('audio') || lk.includes('sound') || lk.includes('voice')
                      combinedMedia.push({
                        id: assetId,
                        field_name: fieldName,
                        filename: `${assetId}`,
                        mime_type: isAudio ? 'audio/mpeg' : 'image/jpeg',
                        sha256: '',
                        proxy_url: pUrl,
                      })
                      existingProxyUrls.add(pUrl)
                    }
                  }
                }
              }
            }

            const mergedFieldValues = {
              ...existingContent.field_values,
              ...newFieldValues,
            }

            const nextRenderContext = patchRenderContext(
              existingContent.render_context || {},
              newFieldValues,
              template?.field_defs,
              combinedMedia,
            )

            const nextVersion = canonicalDigest({
              schema_version: 'study-content.v1',
              renderer_abi: existingContent.renderer_abi,
              note_id: existingContent.note_id,
              field_values: mergedFieldValues,
              media: combinedMedia,
            })
            const newContentKey = `${existingContent.id}:${nextVersion}`

            snapshot.contents[newContentKey] = {
              ...existingContent,
              version: nextVersion,
              field_values: mergedFieldValues,
              render_context: nextRenderContext,
              media: combinedMedia,
            }
            card.content_key = newContentKey
            updated = true
          }
        }
      }
      if (updated) {
        await saveStudySession(session)
      }
    }

    // Broadcast synchronization event to any active study sessions (in current window & across tabs)
    if (typeof window !== 'undefined') {
      window.dispatchEvent(
        new CustomEvent('flama_study_card_updated', {
          detail: {
            cardId,
            noteId: options?.noteId || null,
            fieldValues: newFieldValues,
            media: options?.media,
          },
        }),
      )
      try {
        const channel = new BroadcastChannel('flama_study_sync_channel')
        channel.postMessage({
          type: 'CARD_UPDATED',
          cardId,
          noteId: options?.noteId || null,
          fieldValues: newFieldValues,
          media: options?.media,
        })
        channel.close()
      } catch {
        // BroadcastChannel unavailable
      }
    }
  } catch {
    // Ignore errors if storage is temporarily unaccessible
  }
}

export type UpdatedTemplatePayload = {
  front_html?: string
  back_html?: string
  shared_css?: string
  front_source?: string
  back_source?: string
  front_inline_scripts?: string[]
  back_inline_scripts?: string[]
}

export async function updateTemplateInSessions(
  templateId: string,
  updated: UpdatedTemplatePayload,
) {
  // Template definitions and executable sources are immutable for an open
  // lease. The authoring update is visible only after a new session is opened.
  void templateId
  void updated
}

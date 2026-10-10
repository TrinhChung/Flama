import type { SchedulerCardState } from '../scheduler/types'
import type {
  StudyBatchPayload,
  StudyMediaArtifact,
  StudySessionEvent,
  StudySessionCard,
  StudySessionSnapshot,
} from '../types'
import {
  normalizePersistedStudySession,
} from './sessionRestore'
import type { StudySessionQuarantine } from './sessionRestore'
import { applyCardContentPatch } from './contentPatchAdapter'
import { dispatchStudyCardUpdate } from '@/entities/flashcard/model/studySyncEvents'
import {
  artifactKeyForCheckpoint, artifactsForRestoredSession, hydrateStoredCheckpoint,
  splitSessionCheckpoint, type StoredSessionArtifacts,
} from './sessionStorageCodec'

const DB_NAME = 'flama-study'
// Roll out the writer separately; the reader always understands both layouts.
const SPLIT_STORAGE_ENABLED = import.meta.env.VITE_STUDY_SPLIT_STORAGE_ENABLED === '1'
const DB_VERSION = SPLIT_STORAGE_ENABLED ? 3 : 2
const STORE_NAME = 'sessions'
const QUARANTINE_STORE_NAME = 'session-quarantine'
const ARTIFACT_STORE_NAME = 'session-artifacts'
const durableArtifacts = new Map<string, StoredSessionArtifacts>()
const memoryFallback = new Map<string, PersistedStudySession>()
// A failed write must not be replaced by an older durable row in this tab.
const dirtyMemoryScopes = new Set<string>()
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
    const connect = (version?: number) => {
      const request = version === undefined ? indexedDB.open(DB_NAME) : indexedDB.open(DB_NAME, version)
      let blocked = false
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
        if (SPLIT_STORAGE_ENABLED && !database.objectStoreNames.contains(ARTIFACT_STORE_NAME)) {
          const store = database.createObjectStore(ARTIFACT_STORE_NAME, { keyPath: 'id' })
          store.createIndex('scope_key', 'scope_key')
        }
      }
      request.onsuccess = () => {
        const database = request.result
        database.onversionchange = () => database.close()
        if (blocked) database.close()
        else resolve(database)
      }
      request.onerror = () => {
        // Turning the writer off cannot downgrade IndexedDB. Reopen the current
        // version and keep the split reader so already saved answers remain usable.
        if (request.error?.name === 'VersionError' && version === 2) connect()
        else reject(request.error)
      }
      request.onblocked = () => {
        blocked = true
        reject(new Error('Study storage upgrade is blocked by another tab.'))
      }
    }
    connect(DB_VERSION)
  })
}

function sessionStores(database: IDBDatabase, includeQuarantine = false) {
  return [STORE_NAME, ...(includeQuarantine ? [QUARANTINE_STORE_NAME] : []),
    ...(database.objectStoreNames.contains(ARTIFACT_STORE_NAME) ? [ARTIFACT_STORE_NAME] : [])]
}

function deleteArtifactsForScope(store: IDBObjectStore, key: string, retainedId?: string) {
  const request = store.index('scope_key').getAllKeys(key)
  request.onsuccess = () => {
    for (const id of request.result) if (id !== retainedId) store.delete(id)
  }
}

async function writeStoredSession(session: PersistedStudySession) {
  const database = await openDatabase()
  if (!SPLIT_STORAGE_ENABLED) {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(sessionStores(database), 'readwrite')
      transaction.objectStore(STORE_NAME).put(session)
      if (transaction.objectStoreNames.contains(ARTIFACT_STORE_NAME)) {
        deleteArtifactsForScope(transaction.objectStore(ARTIFACT_STORE_NAME), session.scope_key)
      }
      transaction.oncomplete = () => { database.close(); durableArtifacts.delete(session.scope_key); resolve() }
      transaction.onabort = () => { database.close(); reject(transaction.error) }
      transaction.onerror = () => reject(transaction.error)
    })
    return
  }
  const { checkpoint, artifacts } = splitSessionCheckpoint(session, durableArtifacts.get(session.scope_key))
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction([STORE_NAME, ARTIFACT_STORE_NAME], 'readwrite')
    const artifactStore = transaction.objectStore(ARTIFACT_STORE_NAME)
    const checkpointStore = transaction.objectStore(STORE_NAME)
    // A different tab may have replaced this scope since our last save. Check
    // the immutable row's key, without reading/copying its large payload.
    const request = artifactStore.getKey(artifacts.id)
    request.onsuccess = () => {
      if (request.result === undefined) artifactStore.put(artifacts)
      checkpointStore.put(checkpoint)
      deleteArtifactsForScope(artifactStore, session.scope_key, artifacts.id)
    }
    request.onerror = () => transaction.abort()
    transaction.oncomplete = () => {
      database.close()
      durableArtifacts.set(session.scope_key, artifacts)
      resolve()
    }
    transaction.onabort = () => {
      database.close()
      reject(transaction.error)
    }
    transaction.onerror = () => reject(transaction.error)
  })
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
  dirtyMemoryScopes.delete(key)
  durableArtifacts.delete(key)
  rememberQuarantine(row)

  const database = await openDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(
      sessionStores(database, true),
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
      if (transaction.objectStoreNames.contains(ARTIFACT_STORE_NAME)) {
        deleteArtifactsForScope(transaction.objectStore(ARTIFACT_STORE_NAME), key)
      }

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
    artifactKey: string | null
    artifactCards: StudySessionCard[] | null
  }>((resolve, reject) => {
    const transaction = database.transaction(
      sessionStores(database, true),
      'readonly',
    )
    const activeRequest = transaction.objectStore(STORE_NAME).get(key)
    const quarantineRequest = transaction.objectStore(QUARANTINE_STORE_NAME).get(key)
    let active: unknown
    let artifactKey: string | null = null
    let artifactCards: StudySessionCard[] | null = null
    activeRequest.onsuccess = () => {
      active = activeRequest.result
      artifactKey = artifactKeyForCheckpoint(active)
      if (artifactKey && transaction.objectStoreNames.contains(ARTIFACT_STORE_NAME)) {
        const artifactsRequest = transaction.objectStore(ARTIFACT_STORE_NAME).get(artifactKey)
        artifactsRequest.onsuccess = () => {
          active = hydrateStoredCheckpoint(active, artifactsRequest.result)
          artifactCards = artifactsRequest.result?.cards ?? null
        }
      }
    }
    transaction.oncomplete = () => {
      database.close()
      resolve({
        active,
        artifactKey,
        artifactCards,
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
      dirtyMemoryScopes.delete(key)
      durableArtifacts.delete(key)
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
      durableArtifacts.delete(key)
      return {
        session: null,
        durable: false,
        quarantine: quarantineResult(memoryBlocked),
      }
    }
    const dirtyFallback = dirtyMemoryScopes.has(key) ? memoryFallback.get(key) : undefined
    const restored = dirtyFallback ?? row ?? memoryFallback.get(key) ?? null
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
    if (!dirtyFallback && row && stored.artifactKey && stored.artifactCards) {
      durableArtifacts.set(key, artifactsForRestoredSession(normalized, stored.artifactKey, stored.artifactCards))
    } else if (!dirtyFallback) durableArtifacts.delete(key)
    let durable = Boolean(row) && !dirtyFallback
    if (!dirtyFallback && row && result.migrated) {
      try {
        await writeStoredSession(normalized)
      } catch {
        durable = false
        dirtyMemoryScopes.add(key)
      }
    }
    return { session: normalized, durable }
  } catch {
    const blocked = memoryQuarantine.get(key)
    if (blocked) {
      durableArtifacts.delete(key)
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
      dirtyMemoryScopes.delete(key)
      durableArtifacts.delete(key)
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
  dirtyMemoryScopes.add(normalized.scope_key)
  try {
    await writeStoredSession(normalized)
    if (memoryFallback.get(normalized.scope_key) === normalized) {
      dirtyMemoryScopes.delete(normalized.scope_key)
    }
    return true
  } catch {
    // In private or quota-constrained contexts the in-memory copy still keeps
    // the current tab functional. The UI can continue and commit normally.
    return false
  }
}

export async function removeStudySession(key: string) {
  memoryFallback.delete(key)
  dirtyMemoryScopes.delete(key)
  durableArtifacts.delete(key)
  try {
    const database = await openDatabase()
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(sessionStores(database), 'readwrite')
      transaction.objectStore(STORE_NAME).delete(key)
      if (transaction.objectStoreNames.contains(ARTIFACT_STORE_NAME)) {
        deleteArtifactsForScope(transaction.objectStore(ARTIFACT_STORE_NAME), key)
      }
      transaction.oncomplete = () => { database.close(); resolve() }
      transaction.onabort = () => { database.close(); reject(transaction.error) }
      transaction.onerror = () => reject(transaction.error)
    })
  } catch {
    // Already removed from the current tab fallback.
  }
}

/**
 * Move a still-valid local session out of the active store, keeping its
 * bounded raw copy, when the server already settled its lease another way.
 * The scope reopens only after the user acknowledges the quarantine.
 */
export async function quarantineStudySession(
  key: string,
  session: PersistedStudySession,
  quarantine: StudySessionQuarantine,
) {
  try {
    await moveSessionToQuarantine(key, session, quarantine)
  } catch {
    // Keep at least this tab from resubmitting the lease.
    memoryFallback.delete(key)
    rememberQuarantine({
      scope_key: key,
      quarantined_at_ms: Date.now(),
      reason: quarantine.reason,
      message: quarantine.message,
      ...quarantineEvidence(session),
    })
  }
}

export async function removeStudySessionIfMatches(
  key: string,
  sessionId: string,
) {
  if (memoryFallback.get(key)?.snapshot.session_id === sessionId) {
    memoryFallback.delete(key)
  }
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
      const { updated, nextSession } = applyCardContentPatch(
        session,
        cardId,
        newFieldValues,
        options,
      )
      if (updated) {
        await saveStudySession(nextSession)
      }
    }

    // Broadcast synchronization event to any active study sessions (in current window & across tabs)
    dispatchStudyCardUpdate({
      cardId,
      noteId: options?.noteId || null,
      fieldValues: newFieldValues,
      media: options?.media,
    })
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

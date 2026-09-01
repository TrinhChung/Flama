import type { SchedulerCardState } from '../scheduler/types'
import type {
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'
import {
  normalizePersistedStudySession,
} from './sessionRestore'
import type { StudySessionQuarantine } from './sessionRestore'

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

export type PersistedStudySession = {
  scope_key: string
  snapshot: StudySessionSnapshot
  events: StudySessionEvent[]
  touched_card_ids: string[]
  undo_history?: StudySessionUndoItem[]
  active_card_id?: string | null
  opened_client_at_ms: number
  status: 'active' | 'pending_commit'
  commit_id: string | null
  commit_reason: StudyCommitReason | null
  resume_after_commit: boolean
  updated_at_ms: number
}

type QuarantinedStudySessionRow = {
  scope_key: string
  quarantined_at_ms: number
  reason: StudySessionQuarantine['reason']
  message: string
  raw_session: unknown
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
  const row: QuarantinedStudySessionRow = {
    scope_key: key,
    quarantined_at_ms: quarantinedAtMs,
    reason: quarantine.reason,
    message: quarantine.message,
    raw_session: rawSession,
  }
  memoryFallback.delete(key)
  memoryQuarantine.set(key, row)

  const database = await openDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(
      [STORE_NAME, QUARANTINE_STORE_NAME],
      'readwrite',
    )
    transaction.objectStore(QUARANTINE_STORE_NAME).put(row)
    transaction.objectStore(STORE_NAME).delete(key)
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

export async function loadStudySessionWithDurability(
  key: string,
): Promise<LoadedStudySession> {
  try {
    const row = await transact<unknown | undefined>(
      'readonly',
      (store) => store.get(key),
    )
    const restored = row ?? memoryFallback.get(key) ?? null
    if (!restored) return { session: null, durable: true }
    const result = normalizePersistedStudySession(restored)
    if (result.status === 'quarantine') {
      try {
        await moveSessionToQuarantine(key, restored, result.quarantine)
      } catch {
        // The invalid row is removed from the active in-memory store even if
        // durable quarantine is temporarily unavailable.
      }
      return {
        session: null,
        durable: Boolean(row),
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
    const fallback = memoryFallback.get(key) ?? null
    if (!fallback) return { session: null, durable: false }
    const result = normalizePersistedStudySession(fallback)
    if (result.status === 'quarantine') {
      memoryFallback.delete(key)
      const quarantinedAtMs = Date.now()
      const row: QuarantinedStudySessionRow = {
        scope_key: key,
        quarantined_at_ms: quarantinedAtMs,
        reason: result.quarantine.reason,
        message: result.quarantine.message,
        raw_session: fallback,
      }
      memoryQuarantine.set(key, row)
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

export async function loadStudySession(key: string) {
  return (await loadStudySessionWithDurability(key)).session
}

export async function saveStudySession(session: PersistedStudySession) {
  const result = normalizePersistedStudySession(session)
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
  options?: { noteId?: string | null },
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
          if (snapshot.contents[contentKey]) {
            snapshot.contents[contentKey] = {
              ...snapshot.contents[contentKey],
              field_values: {
                ...snapshot.contents[contentKey].field_values,
                ...newFieldValues,
              },
            }
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

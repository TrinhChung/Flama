import type { SchedulerCardState } from '../scheduler/types'
import type {
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'

const DB_NAME = 'flama-study'
const DB_VERSION = 1
const STORE_NAME = 'sessions'
const memoryFallback = new Map<string, PersistedStudySession>()

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

const VALID_CARD_TYPES = new Set([
  'new',
  'learning',
  'review',
  'relearning',
])

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isFiniteTimestamp(value: unknown) {
  return typeof value === 'string' && Number.isFinite(Date.parse(value))
}

export function isRestorableStudySession(
  value: unknown,
): value is PersistedStudySession {
  if (!isRecord(value) || !isRecord(value.snapshot)) return false
  const snapshot = value.snapshot
  const policies = snapshot.policies
  const templates = snapshot.templates
  const contents = snapshot.contents
  if (
    snapshot.schema_version !== 'study-session.v2'
    || !isFiniteTimestamp(snapshot.server_now_utc)
    || !isFiniteTimestamp(snapshot.expires_at)
    || typeof snapshot.learn_ahead_seconds !== 'number'
    || !Number.isFinite(snapshot.learn_ahead_seconds)
    || snapshot.learn_ahead_seconds < 0
    || !Array.isArray(snapshot.cards)
    || !isRecord(policies)
    || !isRecord(templates)
    || !isRecord(contents)
  ) return false

  if (!snapshot.cards.every((card) => {
    if (!isRecord(card) || !isRecord(card.state)) return false
    const policyKey = String(card.policy_key || '')
    const templateKey = String(card.template_key || '')
    const contentKey = String(card.content_key || '')
    return (
      typeof card.card_id === 'string'
      && VALID_CARD_TYPES.has(String(card.state.type || ''))
      && isRecord(policies[policyKey])
      && isRecord(templates[templateKey])
      && isRecord(contents[contentKey])
    )
  })) return false

  const activeCardIdValid = (
    value.active_card_id === undefined
    || value.active_card_id === null
    || typeof value.active_card_id === 'string'
  )

  return (
    typeof value.scope_key === 'string'
    && Array.isArray(value.events)
    && Array.isArray(value.touched_card_ids)
    && typeof value.opened_client_at_ms === 'number'
    && Number.isFinite(value.opened_client_at_ms)
    && (value.status === 'active' || value.status === 'pending_commit')
    && activeCardIdValid
  )
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
}

export async function loadStudySessionWithDurability(
  key: string,
): Promise<LoadedStudySession> {
  try {
    const row = await transact<PersistedStudySession | undefined>(
      'readonly',
      (store) => store.get(key),
    )
    const restored = row ?? memoryFallback.get(key) ?? null
    if (!restored) return { session: null, durable: true }
    if (!isRestorableStudySession(restored)) {
      memoryFallback.delete(key)
      try {
        await transact<undefined>('readwrite', (store) => store.delete(key))
      } catch {
        // A malformed durable row is already ignored by the current tab.
      }
      return { session: null, durable: true }
    }
    const normalized = {
      ...restored,
      undo_history: Array.isArray(restored.undo_history) ? restored.undo_history : [],
      commit_reason: restored.commit_reason ?? null,
      resume_after_commit: Boolean(restored.resume_after_commit),
    }
    memoryFallback.set(key, normalized)
    return { session: normalized, durable: Boolean(row) }
  } catch {
    const fallback = memoryFallback.get(key) ?? null
    return {
      session: isRestorableStudySession(fallback) ? fallback : null,
      durable: false,
    }
  }
}

export async function loadStudySession(key: string) {
  return (await loadStudySessionWithDurability(key)).session
}

export async function saveStudySession(session: PersistedStudySession) {
  memoryFallback.set(session.scope_key, session)
  try {
    await transact<IDBValidKey>('readwrite', (store) => store.put(session))
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
        if (card.card_id === cardId) {
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
  } catch {
    // Ignore errors if storage is temporarily unaccessible
  }
}

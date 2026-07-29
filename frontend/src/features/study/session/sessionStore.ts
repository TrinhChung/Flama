import type {
  StudySessionEvent,
  StudySessionSnapshot,
} from '../types'

const DB_NAME = 'flama-study'
const DB_VERSION = 1
const STORE_NAME = 'sessions'
const memoryFallback = new Map<string, PersistedStudySession>()

export type PersistedStudySession = {
  scope_key: string
  snapshot: StudySessionSnapshot
  events: StudySessionEvent[]
  touched_card_ids: string[]
  opened_client_at_ms: number
  status: 'active' | 'pending_commit'
  commit_id: string | null
  resume_after_commit: boolean
  updated_at_ms: number
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

export async function loadStudySession(key: string) {
  try {
    const row = await transact<PersistedStudySession | undefined>(
      'readonly',
      (store) => store.get(key),
    )
    const restored = row ?? memoryFallback.get(key) ?? null
    if (!restored) return null
    const normalized = {
      ...restored,
      resume_after_commit: Boolean(restored.resume_after_commit),
    }
    memoryFallback.set(key, normalized)
    return normalized
  } catch {
    return memoryFallback.get(key) ?? null
  }
}

export async function saveStudySession(session: PersistedStudySession) {
  memoryFallback.set(session.scope_key, session)
  try {
    await transact<IDBValidKey>('readwrite', (store) => store.put(session))
  } catch {
    // In private or quota-constrained contexts the in-memory copy still keeps
    // the current tab functional. The UI can continue and commit normally.
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

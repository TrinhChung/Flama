export interface AnkiSyncProfile {
  id: string
  flamaUserId: number
  ankiEndpoint: string
  deckName: string
  noteType: string
  mappingJson: Record<string, string>
  updatedAt: string
}

export type SyncNoteStatus = 'New' | 'Changed' | 'Unchanged' | 'Invalid' | 'Syncing' | 'Synced' | 'Error'

export interface AnkiNoteSyncState {
  key: string
  sourceKey: string
  ankiNoteId: number
  ankiDeckName: string
  ankiNoteType: string
  flamaCardId?: string | number | null
  contentHash: string
  lastSyncedAt?: string
  syncStatus: SyncNoteStatus
  lastError?: string
  syncProfileId?: string
}

export interface AnkiMediaSyncState {
  key: string
  sourceKey: string
  fileName: string
  contentHash: string
  flamaMediaId: string
  mimeType: string
  fileSize: number
  lastSyncedAt: string
}

export const DB_NAME = 'FlamaAnkiSyncDB_v2'
export const DB_VERSION = 1

export function openSyncDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains('profiles')) db.createObjectStore('profiles', { keyPath: 'id' })
      if (!db.objectStoreNames.contains('noteStates')) db.createObjectStore('noteStates', { keyPath: 'key' })
      if (!db.objectStoreNames.contains('mediaStates')) db.createObjectStore('mediaStates', { keyPath: 'key' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export function noteStateKey(sourceKey: string, ankiNoteId: number): string {
  return JSON.stringify([sourceKey, ankiNoteId])
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

export async function getNoteSyncState(sourceKey: string, ankiNoteId: number): Promise<AnkiNoteSyncState | null> {
  const db = await openSyncDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction('noteStates', 'readonly')
    const req = tx.objectStore('noteStates').get(noteStateKey(sourceKey, ankiNoteId))
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

export async function saveNoteSyncState(state: Omit<AnkiNoteSyncState, 'key'> & { key?: string }): Promise<void> {
  const db = await openSyncDB()
  const persisted = { ...state, key: state.key || noteStateKey(state.sourceKey, state.ankiNoteId) }
  return new Promise((resolve, reject) => {
    const tx = db.transaction('noteStates', 'readwrite')
    tx.objectStore('noteStates').put(persisted)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

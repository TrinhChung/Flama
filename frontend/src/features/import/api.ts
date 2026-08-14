import { apiRequest } from '@/shared/api/client'

export interface AnkiImportNoteTypePlan {
  sourceModelId: string
  sourceModelName: string
  targetNoteTypeId?: string
  fields: Array<{ name: string; fieldType: string }>
  templates: Array<{
    name: string
    frontHtml: string
    backHtml: string
    sharedCss: string
  }>
  fieldMapping: Record<string, string>
}

export interface AnkiImportSessionPayload {
  source?: string
  sourceKey: string
  sourceAliases?: string[]
  sourceRootPath: string
  targetRootPath: string
  selectedDecks: string[]
  decks: Array<{ sourceDeckId: string; sourcePath: string; targetPath: string }>
  totalNotes: number
  totalMedia: number
  appVersion?: string
  mode: 'strict' | 'auto_sync_missing'
  noteTypes: AnkiImportNoteTypePlan[]
  planHash: string
}

export interface AnkiImportSessionResult {
  importSessionId: string
  status: string
  noteTypeBindings: Record<
    string,
    {
      sourceModelName: string
      targetNoteTypeId: string
      fieldMapping: Record<string, string>
      schemaHash: string
    }
  >
  blockers: Array<{
    sourceModelId: string
    sourceModelName: string
    code: string
    message: string
  }>
  selectedDecks: string[]
}

export interface AnkiImportCapabilities {
  formatVersion: number
  syncFormatVersion?: number
  mediaPackageMaxBytes: number
  mediaPackageMaxEntries: number
  mediaPackageMaxUncompressedBytes: number
  mediaFileMaxBytes: number
  cardBatchMaxItems: number
  cardPackageTargetItems: number
  cardPackageMaxItems: number
  cardPackageMaxBytes: number
  cardPackageMaxUncompressedBytes: number
  progressBatchMaxItems: number
  reviewBatchMaxItems: number
  reviewSessionMaxItems: number
  supportedMediaExtensions: string[]
}

const API_ROOT = '/api/flashcards/import/anki'

export const ankiImportApi = {
  createSession(payload: AnkiImportSessionPayload) {
    return apiRequest<AnkiImportSessionResult>(`${API_ROOT}/sessions`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  capabilities() {
    return apiRequest<AnkiImportCapabilities>(`${API_ROOT}/capabilities`)
  },

  getSession(sessionId: string) {
    return apiRequest<{
      importSessionId: string
      status: string
      totalNotes: number
      processedNotes: number
      attemptedNotes: number
      totalMedia: number
      processedMedia: number
      errors: Array<Record<string, unknown>>
    }>(`${API_ROOT}/sessions/${encodeURIComponent(sessionId)}`)
  },

  cancelSession(sessionId: string) {
    return apiRequest<{ importSessionId: string; status: string }>(
      `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}`,
      { method: 'DELETE' },
    )
  },

  getNoteStatuses(
    sessionId: string,
    notes: Array<{
      ankiNoteId: number
      contentHash: string
      cards: Array<{ sourceCardId: number; snapshotHash: string }>
    }>,
  ) {
    return apiRequest<{
      importSessionId: string
      notes: Array<{
        ankiNoteId: number
        state: 'new' | 'changed' | 'unchanged'
        mediaHashes: string[]
        cards: Array<{
          sourceCardId: number
          progressState: 'new' | 'changed' | 'unchanged' | 'local_changed'
          reviewCursor: string | null
        }>
      }>
    }>(`${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/note-status`, {
      method: 'POST',
      body: JSON.stringify({ notes }),
    })
  },

  uploadMediaPackage(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
  ) {
    return apiRequest<{
      packageId: string
      sequence: number
      sha256: string
      itemCount: number
      replayed: boolean
      acceptedFilenames: string[]
      rejectedFilenames: string[]
    }>(
      `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/packages/media/${sequence}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/zip',
          'X-Package-SHA256': sha256,
        },
        body: packageBlob,
      },
    )
  },

  uploadCardPackage(
    sessionId: string,
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    contentEncoding: 'gzip' | 'identity',
  ) {
    return apiRequest<{
      packageId: string
      sequence: number
      sha256: string
      itemCount: number
      replayed: boolean
      results: Array<{
        ankiNoteId?: number
        imported?: boolean
        noteId?: string | number | null
        error?: string
      }>
    }>(
      `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/packages/cards/${sequence}`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/x-ndjson',
          'Content-Encoding': contentEncoding,
          'X-Package-SHA256': sha256,
        },
        body: packageBlob,
      },
    )
  },

  uploadSyncPackage(
    sessionId: string,
    kind: 'progress' | 'reviews',
    sequence: number,
    packageBlob: Blob,
    sha256: string,
    contentEncoding: 'gzip' | 'identity',
  ) {
    return apiRequest<{
      packageId: string
      sequence: number
      sha256: string
      itemCount: number
      replayed: boolean
      status: string
      results: Array<{
        sourceCardId?: number | string
        sourceReviewId?: number | string
        applied?: boolean
        imported?: boolean
        state: string
        error?: string
      }>
    }>(`${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/packages/${kind}/${sequence}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/x-ndjson',
        'Content-Encoding': contentEncoding,
        'X-Package-SHA256': sha256,
      },
      body: packageBlob,
    })
  },

  completeSession(sessionId: string, expectedNotes: number) {
    return apiRequest<{ importSessionId: string; status: string }>(
      `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/complete`,
      { method: 'POST', body: JSON.stringify({ expectedNotes }) },
    )
  },
}

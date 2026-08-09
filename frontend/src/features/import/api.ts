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
  mediaPackageMaxBytes: number
  mediaPackageMaxEntries: number
  mediaPackageMaxUncompressedBytes: number
  mediaFileMaxBytes: number
  cardBatchMaxItems: number
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

  completeSession(sessionId: string) {
    return apiRequest<{ importSessionId: string; status: string }>(
      `${API_ROOT}/sessions/${encodeURIComponent(sessionId)}/complete`,
      { method: 'POST', body: JSON.stringify({}) },
    )
  },
}

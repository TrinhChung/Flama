/**
 * AnkiConnect Client abstraction for communicating with local Anki Desktop (default: http://127.0.0.1:8765).
 */

export type AnkiConnectStatus =
  | 'Connected'
  | 'Anki is not running'
  | 'AnkiConnect is not installed'
  | 'Connection refused'
  | 'Unsupported AnkiConnect version'
  | 'Invalid response'
  | 'Timeout'

export interface AnkiNoteInfo {
  noteId: number
  modelName: string
  tags: string[]
  fields: Record<string, { value: string; order: number }>
  cards?: number[]
}

export interface AnkiCardInfo {
  cardId: number
  fields: Record<string, { value: string; order: number }>
  modelName: string
  deckName: string
  note: number
}

export interface AnkiTemplateInfo {
  name: string
  front: string
  back: string
}

export interface AnkiModelStylingInfo {
  css: string
}

export interface IAnkiConnectClient {
  checkConnection(endpoint?: string): Promise<{ status: AnkiConnectStatus; version?: number; error?: string }>
  getVersion(endpoint?: string): Promise<number>
  getDeckNames(endpoint?: string): Promise<string[]>
  getDeckNamesAndIds(endpoint?: string): Promise<Record<string, number>>
  findNotes(query: string, endpoint?: string): Promise<number[]>
  notesInfo(notes: number[], endpoint?: string): Promise<AnkiNoteInfo[]>
  findCards(query: string, endpoint?: string): Promise<number[]>
  cardsInfo(cards: number[], endpoint?: string): Promise<AnkiCardInfo[]>
  getModelNames(endpoint?: string): Promise<string[]>
  getModelNamesAndIds(endpoint?: string): Promise<Record<string, number>>
  getModelFieldNames(modelName: string, endpoint?: string): Promise<string[]>
  getModelStyling(modelName: string, endpoint?: string): Promise<AnkiModelStylingInfo>
  getModelTemplates(modelName: string, endpoint?: string): Promise<AnkiTemplateInfo[]>
  retrieveMediaFile(filename: string, endpoint?: string): Promise<string | null>
  multi(
    actions: Array<{ action: string; params?: Record<string, any> }>,
    endpoint?: string
  ): Promise<any[]>
}

export class AnkiConnectClient implements IAnkiConnectClient {
  private defaultEndpoint: string
  private timeoutMs: number

  constructor(defaultEndpoint = 'http://127.0.0.1:8765', timeoutMs = 8000) {
    this.defaultEndpoint = defaultEndpoint.replace(/\/+$/, '')
    this.timeoutMs = timeoutMs
  }

  private async request<T>(
    action: string,
    params: Record<string, any> = {},
    endpoint?: string
  ): Promise<T> {
    const targetEndpoint = (endpoint || this.defaultEndpoint).replace(/\/+$/, '')
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs)

    try {
      const res = await fetch(targetEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, version: 6, params }),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!res.ok) {
        throw new Error(`HTTP error ${res.status}`)
      }

      const data = await res.json()
      if (data.error) {
        throw new Error(data.error)
      }
      return data.result as T
    } catch (err: any) {
      clearTimeout(timeoutId)
      if (err?.name === 'AbortError') {
        throw new Error('AnkiConnect request timed out.')
      }
      if (err?.message?.includes('Failed to fetch') || err?.message?.includes('NetworkError')) {
        throw new Error('Connection refused')
      }
      throw err
    }
  }

  async checkConnection(endpoint?: string): Promise<{ status: AnkiConnectStatus; version?: number; error?: string }> {
    try {
      const version = await this.getVersion(endpoint)
      if (version < 6) {
        return { status: 'Unsupported AnkiConnect version', version }
      }
      return { status: 'Connected', version }
    } catch (err: any) {
      const msg = String(err?.message || '')
      if (msg.includes('Connection refused') || msg.includes('Failed to fetch')) {
        return { status: 'Connection refused', error: 'Không thể kết nối tới Anki Desktop (127.0.0.1:8765). Có thể phần mềm Anki chưa bật, thiếu add-on AnkiConnect, hoặc trình duyệt chặn kết nối (lỗi CORS).' }
      }
      if (msg.includes('timed out')) {
        return { status: 'Timeout', error: 'Kết nối AnkiConnect bị quá thời gian (Timeout).' }
      }
      return { status: 'Anki is not running', error: msg || 'Không nhận được phản hồi từ AnkiConnect.' }
    }
  }

  async getVersion(endpoint?: string): Promise<number> {
    return this.request<number>('version', {}, endpoint)
  }

  async getDeckNames(endpoint?: string): Promise<string[]> {
    return this.request<string[]>('deckNames', {}, endpoint)
  }

  async getDeckNamesAndIds(endpoint?: string): Promise<Record<string, number>> {
    try {
      return await this.request<Record<string, number>>('deckNamesAndIds', {}, endpoint)
    } catch {
      const names = await this.getDeckNames(endpoint)
      return Object.fromEntries(names.map((name) => [name, 0]))
    }
  }

  async findNotes(query: string, endpoint?: string): Promise<number[]> {
    return this.request<number[]>('findNotes', { query }, endpoint)
  }

  async notesInfo(notes: number[], endpoint?: string): Promise<AnkiNoteInfo[]> {
    if (!notes || notes.length === 0) return []
    return this.request<AnkiNoteInfo[]>('notesInfo', { notes }, endpoint)
  }

  async findCards(query: string, endpoint?: string): Promise<number[]> {
    return this.request<number[]>('findCards', { query }, endpoint)
  }

  async cardsInfo(cards: number[], endpoint?: string): Promise<AnkiCardInfo[]> {
    if (!cards || cards.length === 0) return []
    return this.request<AnkiCardInfo[]>('cardsInfo', { cards }, endpoint)
  }

  async getModelNames(endpoint?: string): Promise<string[]> {
    return this.request<string[]>('modelNames', {}, endpoint)
  }

  async getModelNamesAndIds(endpoint?: string): Promise<Record<string, number>> {
    try {
      return await this.request<Record<string, number>>('modelNamesAndIds', {}, endpoint)
    } catch {
      const names = await this.getModelNames(endpoint)
      return Object.fromEntries(names.map((name) => [name, 0]))
    }
  }

  async getModelFieldNames(modelName: string, endpoint?: string): Promise<string[]> {
    return this.request<string[]>('modelFieldNames', { modelName }, endpoint)
  }

  async getModelStyling(modelName: string, endpoint?: string): Promise<AnkiModelStylingInfo> {
    try {
      const res = await this.request<{ css: string }>('modelStyling', { modelName }, endpoint)
      return { css: res?.css || '' }
    } catch {
      return { css: '' }
    }
  }

  async getModelTemplates(modelName: string, endpoint?: string): Promise<AnkiTemplateInfo[]> {
    try {
      const res = await this.request<any>('modelTemplates', { modelName }, endpoint)
      if (!res) return []
      if (Array.isArray(res)) {
        return res.map((t: any) => ({
          name: t.Name || t.name || 'Card Template',
          front: t.Front || t.qfmt || '',
          back: t.Back || t.afmt || '',
        }))
      }
      return Object.entries(res).map(([name, tmpl]: [string, any]) => ({
        name,
        front: tmpl.Front || tmpl.qfmt || '',
        back: tmpl.Back || tmpl.afmt || '',
      }))
    } catch {
      return []
    }
  }

  async retrieveMediaFile(filename: string, endpoint?: string): Promise<string | null> {
    if (!filename || !filename.trim()) return null
    try {
      return await this.request<string | null>('retrieveMediaFile', { filename: filename.trim() }, endpoint)
    } catch {
      return null
    }
  }

  async multi(
    actions: Array<{ action: string; params?: Record<string, any> }>,
    endpoint?: string
  ): Promise<any[]> {
    if (!actions || actions.length === 0) return []
    return this.request<any[]>('multi', { actions }, endpoint)
  }
}

export const ankiConnectClient = new AnkiConnectClient()

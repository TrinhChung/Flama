import { API_BASE_URL } from '@/config/env'
import { apiJson, apiRequest } from '@/shared/api/client'
import type { CreateDeckForm, MoveDeckForm, RenameDeckForm } from '../schemas'
import type { DashboardPayload, DeckNode } from '../types'

const API_BASE = API_BASE_URL

type DashboardRow = {
  deck_id: number
  parent_id: number | null
  move_alias?: string
  label: string
  depth: number
  new_count: number
  learn_count: number
  due_count: number
  note_type_id?: string | null
  children: DashboardRow[]
}

type DashboardResponse = {
  items: DashboardRow[]
  admin_mode: boolean
}

export type NoteTypeOption = { id: string; name: string; title?: string }

function toDeckNode(row: DashboardRow): DeckNode {
  return {
    id: row.deck_id,
    parent_id: row.parent_id,
    name: row.label,
    depth: row.depth,
    study_url: `/study?deck_id=${row.deck_id}`,
    note_type_id: row.note_type_id ?? null,
    counts: {
      new: row.new_count,
      learning: row.learn_count,
      due: row.due_count,
    },
    move_alias: row.move_alias,
    share_url: `/marketplace/decks/publish?deck_id=${row.deck_id}`,
    children: row.children.map(toDeckNode),
  }
}

function toDashboard(payload: DashboardResponse): DashboardPayload {
  return {
    decks: payload.items.map(toDeckNode),
    admin_mode: payload.admin_mode,
  }
}

export const dashboardApi = {
  async getDashboard(): Promise<DashboardPayload> {
    const payload = await apiRequest<DashboardResponse>(
      `${API_BASE}/dashboard?compact=1`,
      { includeTimezone: false },
    )
    return toDashboard(payload)
  },

  async listNoteTypes(): Promise<{ items: NoteTypeOption[] }> {
    return apiRequest<{ items: NoteTypeOption[] }>(`${API_BASE}/note-types`)
  },

  async getDeckNoteType(deckId: number): Promise<{ note_type_id: string | null }> {
    return apiRequest<{ note_type_id: string | null }>(`${API_BASE}/decks/${deckId}/note-type`)
  },

  async createDeck(values: CreateDeckForm) {
    return apiJson(`${API_BASE}/decks`, 'POST', {
      name: values.name,
      path: values.deck_path,
      parent_id: values.parent_id || null,
      note_type_id: values.note_type_id || null,
    })
  },

  async renameDeck(deckId: number, values: RenameDeckForm) {
    return apiJson(`${API_BASE}/decks/${deckId}`, 'PATCH', values)
  },

  async moveDeck(deckId: number, values: MoveDeckForm) {
    return apiJson(`${API_BASE}/decks/${deckId}`, 'PATCH', {
      parent_id: values.parent_id || null,
    })
  },

  async deleteDeck(deckId: number, params?: { purge?: boolean }) {
    const suffix = params?.purge ? '?purge=true' : ''
    return apiJson(`${API_BASE}/decks/${deckId}${suffix}`, 'DELETE')
  },

  async resetDeck(deckId: number) {
    return apiJson(`${API_BASE}/decks/${deckId}/progress-reset`, 'POST', {})
  },
}

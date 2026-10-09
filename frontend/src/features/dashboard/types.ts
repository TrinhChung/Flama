export type DeckNode = {
  id: number
  parent_id: number | null
  name: string
  depth: number
  study_url: string
  note_type_id?: string | null
  counts: {
    new: number
    learning: number
    due: number
  }
  move: {
    alias: string
    token: string
    parent_alias: string | null
    parent_token: string | null
  }
  actions: {
    rename: string
    move: string
    delete: string
    reset: string
    share: string
  }
  children: DeckNode[]
}

export type DashboardPayload = {
  decks: DeckNode[]
  totals: {
    new: number
    learning: number
    due: number
  }
  admin_mode: boolean
  stats_initial_year: number
  actions: {
    create: string
    move: string
  }
}

import type {
  HeatmapDay,
  HeatmapOverviewData,
} from '@/shared/types/heatmap'

export type DashboardHeatmapDay = HeatmapDay
export type DashboardOverview = HeatmapOverviewData


export type DeckAction = 'rename' | 'move' | 'reset' | 'delete' | 'worksheet' | 'card-types'

export type SelectedDeckAction = {
  type: DeckAction
  deck: DeckNode
}

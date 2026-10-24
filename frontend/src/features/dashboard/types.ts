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
  /** Display identifier copied from the admin row menu. */
  move_alias?: string
  share_url: string
  children: DeckNode[]
}

export type DashboardPayload = {
  decks: DeckNode[]
  admin_mode: boolean
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

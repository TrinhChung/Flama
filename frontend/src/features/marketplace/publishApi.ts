import { appApi } from '@/app/api'

export type PublishDeckOption = {
  id: number
  name: string
  parent_id: number | null
  card_count: number
  is_selectable: boolean
  block_code: 'marketplace_clone' | 'marketplace_note_type' | 'already_shared' | 'ancestor_shared' | 'descendant_shared' | 'not_owned' | null
  block_reason: string | null
  shared_item_id: string | null
}

export type PublishDeckOptionsResponse = {
  items: PublishDeckOption[]
}

export async function loadDeckOptionsForPublish(): Promise<PublishDeckOptionsResponse> {
  return appApi.get<PublishDeckOptionsResponse>('/api/shared/decks/publish-options')
}

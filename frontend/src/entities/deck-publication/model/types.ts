export type AutoPublishStatus = {
  deck_item_id: string
  content_model?: 'published_base'
  auto_publish_enabled: boolean
  last_auto_published_at?: string | null
  last_auto_publish_error?: string | null
  current_release?: { version_label: string; [metadata: string]: unknown } | null
  pending_changes_count: number
  working_revision: number
}

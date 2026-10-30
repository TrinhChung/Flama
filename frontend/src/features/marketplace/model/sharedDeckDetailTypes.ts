export type AuthorProfile = {
  username?: string
  account_name?: string
  published_count?: number
  total_installs?: number
  avg_rating?: number
}

export type ReviewItem = {
  id?: string
  username?: string
  rating: number
  comment?: string | null
  updated_at?: string | null
}

export type TestSample = {
  note_id?: string
  word?: string
  reading?: string
  meaning?: string
}

export type MarketplaceItemMini = {
  id: string
  title?: string
  name?: string
  price_display?: string
  rating_avg?: number
  author?: { username?: string } | null
  author_filter_token?: string
}

export type TemplateItem = {
  id: string
  name: string
  position?: number
}

export type SourceNoteType = {
  id: string
  title?: string
  name?: string
  templates?: TemplateItem[]
}

export type LessonItem = {
  id: number
  name: string
  parent_id: number | null
  depth: number
  is_root: boolean
  direct_note_count: number
  direct_card_count: number
  note_count: number
  card_count: number
  total_note_count: number
  total_card_count: number
  has_children: boolean
}

export type SharedDeckDetail = {
  id: string
  title?: string
  description?: string | null
  preview_text?: string | null
  primary_category?: string | null
  version?: string
  price_display?: string
  pricing_mode?: string
  rating_avg: number
  rating_count: number
  install_count: number
  note_count?: number
  card_count?: number
  lesson_count?: number
  total_decks?: number
  has_subdecks?: boolean
  lessons?: LessonItem[]
  updated_at?: string
  created_at?: string
  badges?: string[]
  tags?: string[]
  display_tags?: string[]
  is_installed: boolean
  installed_deck_id?: number | null
  is_owner: boolean
  is_saved: boolean
  can_rate: boolean
  review_submission_count?: number
  distribution_mode?: 'free' | 'paid' | 'course_key'
  requires_access_key?: boolean
  course_title?: string | null
  course_description?: string | null
  course_url?: string | null
  course_instructions?: string | null
  student_offer_mode?: string
  student_discount_percent?: number | null
  has_student_offer?: boolean
  student_preview_display?: string
  student_preview_price_minor?: number
  effective_price_amount_minor?: number
  effective_price_display?: string
  discount_amount_minor?: number
  student_discount_applied?: boolean
  user_student_status?: string
  review_submissions_remaining?: number
  my_review?: ReviewItem | null
  author?: { id: number; username: string } | null
  author_profile?: AuthorProfile
  author_other_items?: MarketplaceItemMini[]
  related_items?: MarketplaceItemMini[]
  recent_reviews?: ReviewItem[]
  test_samples?: TestSample[]
  source_deck_id?: number | null
  source_note_type_id?: string | null
  source_note_type?: SourceNoteType | null
  publish_status?: 'private' | 'published' | 'unlisted' | 'archived'
}

export type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

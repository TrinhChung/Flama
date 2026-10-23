export type FieldDef = {
  name: string
  label?: string
  type?: string
}

export type TemplateItem = {
  id: string
  application_id?: string | null
  name: string
  front_html?: string
  back_html?: string
  is_installed?: boolean
  installed_template_id?: string | null
  source_template_id?: string
  author?: { id: number; username: string } | null
  pricing_mode?: 'free' | 'paid'
  price_amount_minor?: number
  already_entitled?: boolean
  is_owned_by_author?: boolean
}

/** A template can occur more than once with different note-field bindings. */
export function templateOccurrenceId(template: TemplateItem): string {
  return template.application_id || template.id
}

export function canonicalTemplateId(template: TemplateItem): string {
  return template.source_template_id || template.id
}

export type ReviewItem = {
  id?: string
  username?: string
  rating: number
  comment?: string | null
  updated_at?: string | null
}

export type SharedNoteTypeDetail = {
  id: string
  name?: string
  title?: string
  description?: string | null
  preview_text?: string | null
  primary_category?: string | null
  price_display?: string
  pricing_mode?: string
  rating_avg: number
  rating_count: number
  install_count: number
  updated_at?: string
  badges?: string[]
  tags?: string[]
  display_tags?: string[]
  is_installed: boolean
  installed_note_type_id?: string | null
  is_owner: boolean
  is_saved: boolean
  can_rate: boolean
  review_submission_count?: number
  review_submissions_remaining?: number
  my_review?: ReviewItem | null
  author?: { id: number; username: string } | null
  author_profile?: {
    username?: string
    published_count?: number
  }
  field_defs?: FieldDef[]
  templates?: TemplateItem[]
  recent_reviews?: ReviewItem[]
  pricing_breakdown?: NoteTypePricingBreakdown
  publish_status?: 'private' | 'published' | 'unlisted' | 'archived'
}

export type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export type NoteTypePricingBreakdown = {
  available?: boolean
  bundle_amount_minor: number
  template_amount_minor: number
  total_amount_minor: number
  payment_required: boolean
  templates: {
    template_id: string
    name: string
    author: { id: number; username: string }
    pricing_mode: 'free' | 'paid'
    price_amount_minor: number
    charge_amount_minor: number
    is_owned_by_author: boolean
    already_entitled: boolean
  }[]
}
export type InstallResult = {
  local_template_id?: string
  source_template_id?: string
  already_installed?: boolean
  payment_required?: boolean
  order?: { active_attempt?: { checkout_url?: string } | null }
}

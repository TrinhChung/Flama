export type MarketTemplatePricing = 'free' | 'paid'
export type MarketTemplateSort = 'newest' | 'popular' | 'price_asc' | 'price_desc' | 'name'

export type MarketTemplateInput = {
  key: string
  label: string
  type: string
}

export type MarketTemplateItem = {
  id: string
  name: string
  description: string
  primary_category: string | null
  pricing_mode: MarketTemplatePricing
  price_amount_minor: number
  price_display: string
  install_count: number
  published_at: string | null
  version_label: string | null
  release_published_at: string | null
  inputs: MarketTemplateInput[]
  input_count: number
  author: { id: number; username: string | null }
  is_owner: boolean
  is_installed: boolean
  installed_template_id: string | null
  is_purchased: boolean
  is_listed: boolean
}

export type MarketTemplateRelease = {
  id: string
  version_label: string
  change_note: string | null
  published_at: string | null
}

export type MarketTemplateDetail = MarketTemplateItem & {
  release_change_note: string | null
  updated_at: string | null
  recent_releases: MarketTemplateRelease[]
}

export type MarketTemplateCategory = { name: string; count: number }

export type MarketTemplateCatalog = {
  items: MarketTemplateItem[]
  categories: MarketTemplateCategory[]
  pagination: { page: number; page_size: number; total: number; has_more: boolean }
}

export type MarketTemplateParams = {
  q?: string
  category?: string
  pricing_mode?: MarketTemplatePricing
  sort?: MarketTemplateSort
  page?: number
  page_size?: number
}

export type MarketTemplatePreview = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}

export type MarketTemplateInstallResult = {
  already_installed?: boolean
  local_template_id?: string
  source_template_id?: string
  payment_required?: boolean
  order?: { active_attempt?: { checkout_url?: string | null } | null }
}

export type TemplateListingStatus = 'private' | 'published'

export type TemplateListing = {
  template_id: string
  can_publish: boolean
  block_code: string | null
  block_reason: string | null
  missing_requirements: string[]
  marketplace_status: TemplateListingStatus
  pricing_mode: MarketTemplatePricing
  price_amount_minor: number
  price_display: string
  published_at: string | null
  current_release: { id: string; version_label: string; published_at: string | null } | null
  has_unpublished_changes: boolean
  install_count: number
}

export type TemplateListingBody = {
  marketplace_status?: TemplateListingStatus
  pricing_mode?: MarketTemplatePricing
  price_amount_minor?: number
}

export type ProfileUserRole = {
  id: number
  code: string
  name: string
  description?: string | null
  is_admin: boolean
}

export type SocialLink = {
  type:
    | 'website'
    | 'github'
    | 'youtube'
    | 'facebook'
    | 'x'
    | 'twitter'
    | 'linkedin'
    | 'instagram'
    | 'discord'
    | 'other'
    | string
  url: string
  label?: string
}

export type ProfileUser = {
  id: number
  username: string
  display_name?: string | null
  email?: string
  avatar_url?: string | null
  bio?: string | null
  social_links?: SocialLink[]
  timezone?: string
  is_admin?: boolean
  is_disabled?: boolean
  created_at: string | null
  email_verified?: boolean
  email_verified_at?: string | null
  email_verification_source?: string | null
  student_status?: 'not_eligible' | 'eligible_unverified_email' | 'verified_student' | string
  is_verified_student?: boolean
  is_edu_email?: boolean
  institution_domain?: string | null
  has_password?: boolean
  role: ProfileUserRole | null
}

export type CreatorStats = {
  created_decks_count: number
  created_note_types_count: number
  total_installs_count: number
  rating_count: number
  rating_avg: number
  contributions_merged_count: number
  total_contributions_count: number
}

export type ProfileBadge = {
  id: string
  code: string
  name: string
  description: string
  icon: string
  tier: 'system' | 'creator' | 'highlight' | 'community' | 'verified' | string
}

export type PublishedDeck = {
  id: string
  title: string
  description: string
  primary_category: string
  tags: string[]
  sample_cards_count: number
  pricing_mode: string
  price_amount_minor: number
  price_display: string
  install_count: number
  rating_avg: number
  rating_count: number
  version: string
  published_at: string | null
  updated_at: string | null
}

export type PublishedNoteType = {
  id: string
  name: string
  description: string
  primary_category: string
  tags: string[]
  preview_text?: string | null
  pricing_mode: string
  price_amount_minor: number
  price_display: string
  install_count: number
  rating_avg: number
  rating_count: number
  version: string
  published_at: string | null
  updated_at: string | null
}

export type ContributionItem = {
  id: string
  title: string
  description: string
  status: string
  deck_item_id?: string | null
  deck_title: string
  merged_at: string | null
  created_at: string | null
}

export type PrivateProfileResponse = {
  user: ProfileUser
  creator_stats: CreatorStats
  badges: ProfileBadge[]
  wallet?: any
}

export type PublicProfileResponse = {
  user: ProfileUser
  stats: CreatorStats
  badges: ProfileBadge[]
  published_decks: PublishedDeck[]
  published_note_types: PublishedNoteType[]
  contributions: ContributionItem[]
  is_own_profile: boolean
}

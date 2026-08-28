export type OnboardingSubject =
  | 'japanese'
  | 'english'
  | 'korean'
  | 'chinese'
  | 'it_coding'
  | 'aws'
  | 'thpt_qg'
  | 'medical'
  | 'other'

export type DailyTargetOption = 5 | 10 | 20 | 30

export type StudyTimeOption = 'morning' | 'afternoon' | 'evening'

export interface OnboardingPreferences {
  targetDomain: string
  targetSubject: OnboardingSubject
  frameworkLevel: string
  difficultyBand: 'beginner' | 'intermediate' | 'advanced'
  dailyNewCards: DailyTargetOption
  preferredStudyTime: StudyTimeOption
  installedDeckIds: string[]
  completedAt: string | null
  tourSeen: boolean
}

export interface RecommendedDeckItem {
  id: string
  title: string
  description: string | null
  primary_category: string | null
  card_count?: number
  note_count?: number
  lesson_count?: number
  rating_avg?: number
  rating_count?: number
  install_count?: number
  price_display?: string
  pricing_mode?: string
  is_installed?: boolean
  installed_deck_id?: number | null
  badges?: string[]
  tags?: string[]
  author?: {
    username?: string
  } | null
}

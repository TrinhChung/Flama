import type { Rating } from '../types'

export type SchedulerCardType = 'new' | 'learning' | 'review' | 'relearning'

export type SchedulerMemoryState = {
  stability: number
  difficulty: number
}

export type SchedulerCardState = {
  type: SchedulerCardType
  step_index: number
  due_at: string | null
  due_day: number | null
  interval_days: number
  ease: number
  reps: number
  lapses: number
  last_review_at: string | null
  review_kind: string
  scheduler_mode: string
  suspended: boolean
  suspension_reason: string | null
  leeched: boolean
  memory_state: SchedulerMemoryState | null
}

export type FsrsAnswerState = {
  interval_days: number
  memory: SchedulerMemoryState | null
}

export type SchedulerOptions = {
  learning_steps_ms: number[]
  graduating_interval_days: number
  easy_interval_days: number
  relearning_steps_ms: number[]
  minimum_interval_days: number
  starting_ease: number
  easy_bonus: number
  interval_modifier: number
  hard_factor: number
  new_interval_factor: number
  min_ease: number
  max_interval_days: number
  day_boundary_hour_local: number
  learn_ahead_seconds: number
  leech_threshold: number
  leech_suspend: boolean
  scheduler_mode: string
  review_fuzz_factor: number | null
  fsrs_next_states: Record<Rating, FsrsAnswerState> | null
}

export type SchedulerPreview = {
  seconds: number | null
  days: number | null
  intervalDays: number | null
  label: string
}

export type SchedulerDecision = {
  scheduler_at: string
  scheduler_at_ms: number
  outcomes: Record<Rating, SchedulerCardState>
  previews: Record<Rating, SchedulerPreview>
}

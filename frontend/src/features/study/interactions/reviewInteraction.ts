export const REVIEW_TRIGGER_CONTRACT_VERSION = '1' as const

export const REVIEW_RATINGS = [
  'again',
  'hard',
  'good',
  'easy',
] as const

export type ReviewRating = (typeof REVIEW_RATINGS)[number]

export type ReviewAction = Readonly<{
  rating: ReviewRating
  actionKey: `review.${ReviewRating}`
  triggerKey: `scheduler.review.${ReviewRating}`
  triggerContractVersion: typeof REVIEW_TRIGGER_CONTRACT_VERSION
}>

const REVIEW_ACTIONS = Object.fromEntries(
  REVIEW_RATINGS.map((rating) => [
    rating,
    Object.freeze({
      rating,
      actionKey: `review.${rating}`,
      triggerKey: `scheduler.review.${rating}`,
      triggerContractVersion: REVIEW_TRIGGER_CONTRACT_VERSION,
    }),
  ]),
) as Record<ReviewRating, ReviewAction>

export function resolveReviewAction(rating: ReviewRating): ReviewAction {
  return REVIEW_ACTIONS[rating]
}

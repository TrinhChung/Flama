export const REVIEW_TRIGGER_CONTRACT_VERSION = '1' as const
export const REVIEW_ACTION_CONTRACT_VERSION = '1' as const

export const REVIEW_RATINGS = [
  'again',
  'hard',
  'good',
  'easy',
] as const

export type ReviewRating = (typeof REVIEW_RATINGS)[number]

export type ReviewAction = {
  [Rating in ReviewRating]: Readonly<{
    rating: Rating
    actionKey: `review.${Rating}`
    actionContractVersion: typeof REVIEW_ACTION_CONTRACT_VERSION
    triggerKey: `scheduler.review.${Rating}`
    triggerContractVersion: typeof REVIEW_TRIGGER_CONTRACT_VERSION
  }>
}[ReviewRating]

const REVIEW_ACTIONS = Object.fromEntries(
  REVIEW_RATINGS.map((rating) => [
    rating,
    Object.freeze({
      rating,
      actionKey: `review.${rating}`,
      actionContractVersion: REVIEW_ACTION_CONTRACT_VERSION,
      triggerKey: `scheduler.review.${rating}`,
      triggerContractVersion: REVIEW_TRIGGER_CONTRACT_VERSION,
    }),
  ]),
) as Record<ReviewRating, ReviewAction>

export function resolveReviewAction(rating: ReviewRating): ReviewAction {
  return REVIEW_ACTIONS[rating]
}

/** The only compatibility boundary from semantic UI actions to scheduler ratings. */
export function reviewActionToLegacyRating(action: ReviewAction): ReviewRating {
  const canonical = resolveReviewAction(action.rating)
  if (
    action.actionKey !== canonical.actionKey
    || action.actionContractVersion !== canonical.actionContractVersion
    || action.triggerKey !== canonical.triggerKey
    || action.triggerContractVersion !== canonical.triggerContractVersion
  ) {
    throw new Error('Review action contract is inconsistent.')
  }
  return canonical.rating
}

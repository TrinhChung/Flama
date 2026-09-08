import { describe, expect, it } from 'vitest'
import {
  REVIEW_RATINGS,
  REVIEW_ACTION_CONTRACT_VERSION,
  REVIEW_TRIGGER_CONTRACT_VERSION,
  resolveReviewAction,
  reviewActionToLegacyRating,
} from './reviewInteraction'

describe('built-in review interaction', () => {
  it('maps every visible rating to stable action and trigger identities', () => {
    for (const rating of REVIEW_RATINGS) {
      expect(resolveReviewAction(rating)).toEqual({
        rating,
        actionKey: `review.${rating}`,
        actionContractVersion: REVIEW_ACTION_CONTRACT_VERSION,
        triggerKey: `scheduler.review.${rating}`,
        triggerContractVersion: REVIEW_TRIGGER_CONTRACT_VERSION,
      })
    }
  })

  it('maps a canonical semantic action to the legacy scheduler rating', () => {
    expect(reviewActionToLegacyRating(resolveReviewAction('easy'))).toBe('easy')
  })

  it('rejects an inconsistent action at the compatibility boundary', () => {
    expect(() => reviewActionToLegacyRating({
      rating: 'good',
      actionKey: 'review.good',
      actionContractVersion: '1',
      triggerKey: 'scheduler.review.again',
      triggerContractVersion: '1',
    } as never)).toThrow('Review action contract is inconsistent.')
  })
})

import { describe, expect, it } from 'vitest'
import {
  REVIEW_RATINGS,
  REVIEW_TRIGGER_CONTRACT_VERSION,
  resolveReviewAction,
} from './reviewInteraction'

describe('built-in review interaction', () => {
  it('maps every visible rating to stable action and trigger identities', () => {
    for (const rating of REVIEW_RATINGS) {
      expect(resolveReviewAction(rating)).toEqual({
        rating,
        actionKey: `review.${rating}`,
        triggerKey: `scheduler.review.${rating}`,
        triggerContractVersion: REVIEW_TRIGGER_CONTRACT_VERSION,
      })
    }
  })
})

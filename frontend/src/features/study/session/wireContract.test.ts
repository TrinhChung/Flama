import { describe, expect, it } from 'vitest'
import { resolveReviewAction } from '../interactions/reviewInteraction'
import {
  STUDY_SESSION_SCHEMA_V2,
  STUDY_SESSION_SCHEMA_V3,
  reviewEventWireIdentity,
  validateReviewEventWireIdentity,
  wireEnvelopeForSession,
} from './wireContract'

const policy = {
  algorithm_key: 'legacy-anki',
  algorithm_version: '1.0.0',
  config_schema_version: 'scheduler-config.v1',
  config_hash: 'config-1',
}

describe('Study Session wire contracts', () => {
  it('maps snapshot, commit, and batch envelope versions independently', () => {
    expect(wireEnvelopeForSession(STUDY_SESSION_SCHEMA_V2)).toMatchObject({
      commitSchema: 'study-commit.v1',
      batchSchema: 'study-batch.v1',
    })
    expect(wireEnvelopeForSession(STUDY_SESSION_SCHEMA_V3)).toMatchObject({
      commitSchema: 'study-commit.v2',
      batchSchema: 'study-batch.v2',
    })
    expect(() => wireEnvelopeForSession('study-session.latest')).toThrow(
      /Unsupported Study Session schema/,
    )
  })

  it('builds mandatory v3 identity from the pinned session and policy', () => {
    expect(reviewEventWireIdentity(
      STUDY_SESSION_SCHEMA_V3,
      'session-1',
      resolveReviewAction('good'),
      policy,
    )).toEqual({
      action_key: 'review.good',
      action_contract_version: '1',
      trigger_key: 'scheduler.review.good',
      trigger_contract_version: '1',
      algorithm_key: 'legacy-anki',
      algorithm_version: '1.0.0',
      config_schema_version: 'scheduler-config.v1',
      config_hash: 'config-1',
      study_session_id: 'session-1',
    })
  })

  it('accepts v2 with all semantic fields absent or canonical', () => {
    expect(validateReviewEventWireIdentity(
      { rating: 'good' },
      { schema: STUDY_SESSION_SCHEMA_V2, sessionId: 'session-1', policy },
    ).rating).toBe('good')
    expect(validateReviewEventWireIdentity(
      {
        rating: 'good',
        action_key: 'review.good',
        trigger_key: 'scheduler.review.good',
        trigger_contract_version: '1',
      },
      { schema: STUDY_SESSION_SCHEMA_V2, sessionId: 'session-1', policy },
    ).rating).toBe('good')
  })

  it('rejects partial v2 and missing or mismatched v3 identity', () => {
    expect(() => validateReviewEventWireIdentity(
      { rating: 'perfect' },
      { schema: STUDY_SESSION_SCHEMA_V2, sessionId: 'session-1', policy },
    )).toThrow(/unsupported/)
    expect(() => validateReviewEventWireIdentity(
      { rating: 'good', action_key: 'review.good' },
      { schema: STUDY_SESSION_SCHEMA_V2, sessionId: 'session-1', policy },
    )).toThrow(/partial or v3/)

    const v3 = {
      rating: 'good',
      ...reviewEventWireIdentity(
        STUDY_SESSION_SCHEMA_V3,
        'session-1',
        resolveReviewAction('good'),
        policy,
      ),
    }
    expect(validateReviewEventWireIdentity(
      v3,
      { schema: STUDY_SESSION_SCHEMA_V3, sessionId: 'session-1', policy },
    ).rating).toBe('good')
    expect(() => validateReviewEventWireIdentity(
      { ...v3, trigger_key: 'scheduler.review.easy' },
      { schema: STUDY_SESSION_SCHEMA_V3, sessionId: 'session-1', policy },
    )).toThrow(/trigger_key/)
    const { config_hash: _removed, ...missing } = v3 as Record<string, unknown>
    expect(() => validateReviewEventWireIdentity(
      missing,
      { schema: STUDY_SESSION_SCHEMA_V3, sessionId: 'session-1', policy },
    )).toThrow(/incomplete/)
  })
})

import {
  REVIEW_RATINGS,
  resolveReviewAction,
} from '../interactions/reviewInteraction'
import type { ReviewAction, ReviewRating } from '../interactions/reviewInteraction'

export const STUDY_SESSION_SCHEMA_V2 = 'study-session.v2' as const
export const STUDY_SESSION_SCHEMA_V3 = 'study-session.v3' as const
export const STUDY_SESSION_SCHEMA_V4 = 'study-session.v4' as const
export const STUDY_COMMIT_SCHEMA_V1 = 'study-commit.v1' as const
export const STUDY_COMMIT_SCHEMA_V2 = 'study-commit.v2' as const
export const STUDY_COMMIT_SCHEMA_V3 = 'study-commit.v3' as const
export const STUDY_BATCH_SCHEMA_V1 = 'study-batch.v1' as const
export const STUDY_BATCH_SCHEMA_V2 = 'study-batch.v2' as const
export const STUDY_BATCH_SCHEMA_V3 = 'study-batch.v3' as const

export type StudySessionWireSchema =
  | typeof STUDY_SESSION_SCHEMA_V2
  | typeof STUDY_SESSION_SCHEMA_V3

export type StudyWirePolicyIdentity = Readonly<{
  algorithm_key: string
  algorithm_version: string
  config_schema_version: string
  config_hash: string
}>

export type StudyNoteAuthorityWireIdentity = Readonly<{
  enrollment_epoch: string
  logical_note_key: string
  subject_generation: string
  base_authority_revision: string
  base_authority_state_hash: string
}>

export class StudyWireContractError extends Error {
  readonly code: 'UNSUPPORTED_SESSION_SCHEMA' | 'WIRE_CONTRACT_MISMATCH'

  constructor(
    code: 'UNSUPPORTED_SESSION_SCHEMA' | 'WIRE_CONTRACT_MISMATCH',
    message: string,
  ) {
    super(message)
    this.name = 'StudyWireContractError'
    this.code = code
  }
}

export function wireEnvelopeForSession(schema: string) {
  if (schema === STUDY_SESSION_SCHEMA_V2) {
    return {
      sessionSchema: STUDY_SESSION_SCHEMA_V2,
      commitSchema: STUDY_COMMIT_SCHEMA_V1,
      batchSchema: STUDY_BATCH_SCHEMA_V1,
      requiresSemanticIdentity: false,
    } as const
  }
  if (schema === STUDY_SESSION_SCHEMA_V3) {
    return {
      sessionSchema: STUDY_SESSION_SCHEMA_V3,
      commitSchema: STUDY_COMMIT_SCHEMA_V2,
      batchSchema: STUDY_BATCH_SCHEMA_V2,
      requiresSemanticIdentity: true,
    } as const
  }
  if (schema === STUDY_SESSION_SCHEMA_V4) {
    return {
      sessionSchema: STUDY_SESSION_SCHEMA_V4,
      commitSchema: STUDY_COMMIT_SCHEMA_V3,
      batchSchema: STUDY_BATCH_SCHEMA_V3,
      requiresSemanticIdentity: true,
      requiresNoteAuthorityIdentity: true,
    } as const
  }
  throw new StudyWireContractError(
    'UNSUPPORTED_SESSION_SCHEMA',
    `Unsupported Study Session schema: ${schema || '<missing>'}.`,
  )
}

function isCanonicalDecimal(value: string, minimum: number) {
  return /^(0|[1-9][0-9]*)$/.test(value)
    && BigInt(value) >= BigInt(minimum)
}

export function validateNoteAuthorityWireIdentity(
  identity: StudyNoteAuthorityWireIdentity,
) {
  if (
    !isCanonicalDecimal(identity.enrollment_epoch, 1)
    || !isCanonicalDecimal(identity.subject_generation, 1)
    || !isCanonicalDecimal(identity.base_authority_revision, 0)
    || identity.logical_note_key.length === 0
    || identity.logical_note_key.trim() !== identity.logical_note_key
    || new TextEncoder().encode(identity.logical_note_key).length > 144
    || !/^[0-9a-f]{64}$/.test(identity.base_authority_state_hash)
  ) {
    throw new StudyWireContractError(
      'WIRE_CONTRACT_MISMATCH',
      'Study v4 NOTE authority identity is not canonical.',
    )
  }
  return identity
}

export function reviewEventWireIdentityV4(
  sessionId: string,
  operationKey: string,
  action: ReviewAction,
  policy: StudyWirePolicyIdentity,
  authority: StudyNoteAuthorityWireIdentity,
) {
  if (operationKey.length === 0 || operationKey.trim() !== operationKey) {
    throw new StudyWireContractError(
      'WIRE_CONTRACT_MISMATCH',
      'Study v4 operation key is invalid.',
    )
  }
  const pin = validateNoteAuthorityWireIdentity(authority)
  return {
    ...reviewEventWireIdentity(
      STUDY_SESSION_SCHEMA_V3,
      sessionId,
      action,
      policy,
    ),
    authority_mode: 'NOTE' as const,
    // Snapshot pins carry their own schema tag (and may gain metadata). Only
    // the action identity belongs on the strict backend review-event wire.
    enrollment_epoch: pin.enrollment_epoch,
    logical_note_key: pin.logical_note_key,
    subject_generation: pin.subject_generation,
    base_authority_revision: pin.base_authority_revision,
    base_authority_state_hash: pin.base_authority_state_hash,
    operation_key: operationKey,
  }
}

export function reviewEventWireIdentity(
  schema: StudySessionWireSchema,
  sessionId: string,
  action: ReviewAction,
  policy: StudyWirePolicyIdentity,
) {
  const shared = {
    action_key: action.actionKey,
    trigger_key: action.triggerKey,
    trigger_contract_version: action.triggerContractVersion,
  } as const
  if (schema === STUDY_SESSION_SCHEMA_V2) return shared
  return {
    ...shared,
    action_contract_version: action.actionContractVersion,
    algorithm_key: policy.algorithm_key,
    algorithm_version: policy.algorithm_version,
    config_schema_version: policy.config_schema_version,
    config_hash: policy.config_hash,
    study_session_id: sessionId,
  } as const
}

const V2_FIELDS = [
  'action_key',
  'trigger_key',
  'trigger_contract_version',
] as const

const V3_FIELDS = [
  ...V2_FIELDS,
  'action_contract_version',
  'algorithm_key',
  'algorithm_version',
  'config_schema_version',
  'config_hash',
  'study_session_id',
] as const

const V4_FIELDS = [
  'authority_mode',
  'enrollment_epoch',
  'logical_note_key',
  'subject_generation',
  'base_authority_revision',
  'base_authority_state_hash',
  'operation_key',
] as const

export function validateReviewEventWireIdentity(
  event: Record<string, unknown>,
  options: {
    schema: StudySessionWireSchema
    sessionId: string
    policy: StudyWirePolicyIdentity
  },
): ReviewAction {
  if (typeof event.rating !== 'string') {
    throw new StudyWireContractError(
      'WIRE_CONTRACT_MISMATCH',
      'Study event rating is missing.',
    )
  }
  if (!REVIEW_RATINGS.includes(event.rating as ReviewRating)) {
    throw new StudyWireContractError(
      'WIRE_CONTRACT_MISMATCH',
      'Study event rating is unsupported.',
    )
  }
  const action = resolveReviewAction(event.rating as ReviewRating)
  const presentV2 = V2_FIELDS.filter((field) => field in event)
  if (options.schema === STUDY_SESSION_SCHEMA_V2) {
    const v3OnlyPresent = V3_FIELDS
      .slice(V2_FIELDS.length)
      .some((field) => field in event)
    const v4Present = V4_FIELDS.some((field) => field in event)
    if (v3OnlyPresent || v4Present || (presentV2.length > 0 && presentV2.length !== V2_FIELDS.length)) {
      throw new StudyWireContractError(
        'WIRE_CONTRACT_MISMATCH',
        'Study v2 event contains partial or v3 semantic identity.',
      )
    }
    if (presentV2.length === 0) return action
  } else {
    if (V3_FIELDS.some((field) => (
      typeof event[field] !== 'string' || String(event[field]).length === 0
    ))) {
      throw new StudyWireContractError(
        'WIRE_CONTRACT_MISMATCH',
        'Study v3 event semantic identity is incomplete.',
      )
    }
    if (V4_FIELDS.some((field) => field in event)) {
      throw new StudyWireContractError(
        'WIRE_CONTRACT_MISMATCH',
        'Study v3 event contains v4 NOTE authority identity.',
      )
    }
  }

  const expected = reviewEventWireIdentity(
    options.schema,
    options.sessionId,
    action,
    options.policy,
  )
  for (const [field, expectedValue] of Object.entries(expected)) {
    if (event[field] !== expectedValue) {
      throw new StudyWireContractError(
        'WIRE_CONTRACT_MISMATCH',
        `Study event has inconsistent ${field}.`,
      )
    }
  }
  return action
}

export function validateReviewEventWireIdentityV4(
  event: Record<string, unknown>,
  options: {
    sessionId: string
    policy: StudyWirePolicyIdentity
    authority: StudyNoteAuthorityWireIdentity
  },
): ReviewAction {
  if (
    typeof event.event_id !== 'string'
    || typeof event.rating !== 'string'
    || !REVIEW_RATINGS.includes(event.rating as ReviewRating)
  ) {
    throw new StudyWireContractError(
      'WIRE_CONTRACT_MISMATCH',
      'Study v4 event id or rating is invalid.',
    )
  }
  const action = resolveReviewAction(event.rating as ReviewRating)
  const expected = reviewEventWireIdentityV4(
    options.sessionId,
    event.event_id,
    action,
    options.policy,
    options.authority,
  )
  for (const [field, expectedValue] of Object.entries(expected)) {
    if (event[field] !== expectedValue) {
      throw new StudyWireContractError(
        'WIRE_CONTRACT_MISMATCH',
        `Study v4 event has inconsistent ${field}.`,
      )
    }
  }
  return action
}

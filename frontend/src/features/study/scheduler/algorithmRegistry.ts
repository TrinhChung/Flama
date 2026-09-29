import type {
  StudySessionCard,
  StudySessionPolicy,
  StudySessionSnapshot,
} from '../types'
import { computeDecision } from './legacyEngine'
import type { SchedulerDecision } from './types'
import { NOTE_STORAGE_PROFILE } from './noteStoragePrecision'

export const LEGACY_ANKI_ALGORITHM = Object.freeze({
  key: 'legacy-anki',
  version: '1.0.0',
  stateSchemaVersion: 'anki-card-state.v1',
  configSchemaVersion: 'scheduler-config.v1',
})

export type AlgorithmLifecycleState =
  | 'active'
  | 'deprecated'
  | 'lease-only'
  | 'retired'

export type ClientAlgorithmResolutionPurpose =
  | 'new-session'
  | 'existing-lease'
  | 'accepted-job'

export type ClientAlgorithmUnavailableReason =
  | 'UNKNOWN_VERSION'
  | 'RETIRED'
  | 'PURPOSE_NOT_SUPPORTED'
  | 'EVALUATOR_UNAVAILABLE'

export type ClientAlgorithmIdentity = Readonly<{
  key: string
  version: string
  stateSchemaVersion: string
  configSchemaVersion: string
}>

export type ClientAlgorithmArtifactSupport = Readonly<{
  stateDecoder: boolean
  configDecoder: boolean
  eventHistoryDecoder: boolean
  interactionContractDecoder: boolean
}>

export type ClientAlgorithmSupport = Readonly<{
  identity: ClientAlgorithmIdentity
  lifecycleState: AlgorithmLifecycleState
  artifacts: ClientAlgorithmArtifactSupport
  clientEvaluator: boolean
  newSessionAllowed: boolean
  existingLeaseAllowed: boolean
  acceptedJobAllowed: boolean
  historyReadAllowed: boolean
}>

export class ClientAlgorithmUnavailableError extends Error {
  readonly code = 'ALGORITHM_UNAVAILABLE'
  readonly algorithmKey: string
  readonly algorithmVersion: string
  readonly purpose: ClientAlgorithmResolutionPurpose
  readonly lifecycleState: AlgorithmLifecycleState | null
  readonly reason: ClientAlgorithmUnavailableReason

  constructor(
    algorithmKey: string,
    algorithmVersion: string,
    options: {
      purpose?: ClientAlgorithmResolutionPurpose
      lifecycleState?: AlgorithmLifecycleState | null
      reason?: ClientAlgorithmUnavailableReason
    } = {},
  ) {
    const purpose = options.purpose ?? 'existing-lease'
    super(
      `Study Algorithm ${algorithmKey}/${algorithmVersion} is unavailable `
      + `in this client for ${purpose}.`,
    )
    this.name = 'ClientAlgorithmUnavailableError'
    this.algorithmKey = algorithmKey
    this.algorithmVersion = algorithmVersion
    this.purpose = purpose
    this.lifecycleState = options.lifecycleState ?? null
    this.reason = options.reason ?? 'UNKNOWN_VERSION'
  }
}

export class ClientAlgorithmContractError extends Error {
  readonly code = 'ALGORITHM_CONTRACT_MISMATCH'

  constructor(message: string) {
    super(message)
    this.name = 'ClientAlgorithmContractError'
  }
}

export type ClientStudyAlgorithm = ClientAlgorithmIdentity & Readonly<{
  computeDecision: (
    card: StudySessionCard,
    policy: StudySessionPolicy,
    schedulerAtMs: number,
    timezone: string,
  ) => SchedulerDecision
}>

type ClientAlgorithmRegistration = Readonly<{
  support: ClientAlgorithmSupport
  algorithm: ClientStudyAlgorithm | null
}>

const DEFAULT_ARTIFACT_SUPPORT: ClientAlgorithmArtifactSupport = Object.freeze({
  stateDecoder: true,
  configDecoder: true,
  eventHistoryDecoder: true,
  interactionContractDecoder: true,
})

function registryKey(key: string, version: string) {
  return `${key}\u0000${version}`
}

function lifecycleCapabilities(
  lifecycleState: AlgorithmLifecycleState,
  clientEvaluator: boolean,
) {
  const newSessionAllowed = clientEvaluator
    && (lifecycleState === 'active' || lifecycleState === 'deprecated')
  const existingLeaseAllowed = clientEvaluator && lifecycleState !== 'retired'
  return {
    newSessionAllowed,
    existingLeaseAllowed,
    acceptedJobAllowed: existingLeaseAllowed,
  }
}

export class ClientAlgorithmRegistry {
  private readonly registrations = new Map<string, ClientAlgorithmRegistration>()

  register(
    identity: ClientAlgorithmIdentity,
    options: {
      lifecycleState: AlgorithmLifecycleState
      algorithm?: ClientStudyAlgorithm | null
      artifacts?: ClientAlgorithmArtifactSupport
    },
  ) {
    const normalizedKey = String(identity.key || '').trim()
    const normalizedVersion = String(identity.version || '').trim()
    if (!normalizedKey || !normalizedVersion) {
      throw new Error('Client Algorithm key and version must be non-empty.')
    }

    const key = registryKey(normalizedKey, normalizedVersion)
    if (this.registrations.has(key)) {
      throw new Error(`Duplicate client Algorithm registration: ${key}`)
    }

    const algorithm = options.algorithm ?? null
    if (algorithm && (
      algorithm.key !== normalizedKey
      || algorithm.version !== normalizedVersion
      || algorithm.stateSchemaVersion !== identity.stateSchemaVersion
      || algorithm.configSchemaVersion !== identity.configSchemaVersion
    )) {
      throw new Error('Client Algorithm evaluator identity does not match registration.')
    }
    if (options.lifecycleState !== 'retired' && !algorithm) {
      throw new Error('A supported client Algorithm requires an evaluator.')
    }

    const clientEvaluator = Boolean(algorithm)
      && options.lifecycleState !== 'retired'
    const capabilities = lifecycleCapabilities(
      options.lifecycleState,
      clientEvaluator,
    )
    const artifacts = Object.freeze({
      ...(options.artifacts ?? DEFAULT_ARTIFACT_SUPPORT),
    })
    const support: ClientAlgorithmSupport = Object.freeze({
      identity: Object.freeze({
        ...identity,
        key: normalizedKey,
        version: normalizedVersion,
      }),
      lifecycleState: options.lifecycleState,
      artifacts,
      clientEvaluator,
      ...capabilities,
      historyReadAllowed: artifacts.eventHistoryDecoder,
    })
    this.registrations.set(key, Object.freeze({ support, algorithm }))
  }

  support(key: string, version: string): ClientAlgorithmSupport | null {
    const normalizedKey = String(key || '').trim()
    const normalizedVersion = String(version || '').trim()
    return this.registrations.get(
      registryKey(normalizedKey, normalizedVersion),
    )?.support ?? null
  }

  listSupport(): readonly ClientAlgorithmSupport[] {
    return Object.freeze(
      [...this.registrations.values()]
        .map(({ support }) => support)
        .sort((left, right) => registryKey(
          left.identity.key,
          left.identity.version,
        ).localeCompare(registryKey(
          right.identity.key,
          right.identity.version,
        ))),
    )
  }

  resolve(
    key: string,
    version: string,
    purpose: ClientAlgorithmResolutionPurpose = 'existing-lease',
  ): ClientStudyAlgorithm {
    const normalizedKey = String(key || '').trim()
    const normalizedVersion = String(version || '').trim()
    const registration = this.registrations.get(
      registryKey(normalizedKey, normalizedVersion),
    )
    const displayKey = normalizedKey || '<missing>'
    const displayVersion = normalizedVersion || '<missing>'

    if (!registration) {
      throw new ClientAlgorithmUnavailableError(displayKey, displayVersion, {
        purpose,
      })
    }

    const { support, algorithm } = registration
    const allowed = purpose === 'new-session'
      ? support.newSessionAllowed
      : purpose === 'accepted-job'
        ? support.acceptedJobAllowed
        : support.existingLeaseAllowed
    if (!allowed || !algorithm) {
      const reason: ClientAlgorithmUnavailableReason
        = support.lifecycleState === 'retired'
          ? 'RETIRED'
          : algorithm
            ? 'PURPOSE_NOT_SUPPORTED'
            : 'EVALUATOR_UNAVAILABLE'
      throw new ClientAlgorithmUnavailableError(displayKey, displayVersion, {
        purpose,
        lifecycleState: support.lifecycleState,
        reason,
      })
    }

    return algorithm
  }
}

const algorithmRegistry = new ClientAlgorithmRegistry()

const legacyAnkiClientAlgorithm: ClientStudyAlgorithm = Object.freeze({
  ...LEGACY_ANKI_ALGORITHM,
  computeDecision: (card, policy, schedulerAtMs, timezone) => computeDecision(
    card.state,
    policy.config,
    schedulerAtMs,
    timezone,
  ),
})

algorithmRegistry.register(LEGACY_ANKI_ALGORITHM, {
  lifecycleState: 'active',
  algorithm: legacyAnkiClientAlgorithm,
})

export function resolveClientAlgorithm(
  key: string,
  version: string,
  purpose: ClientAlgorithmResolutionPurpose = 'existing-lease',
) {
  return algorithmRegistry.resolve(key, version, purpose)
}

export function getClientAlgorithmSupport(key: string, version: string) {
  return algorithmRegistry.support(key, version)
}

export function listClientAlgorithmSupport() {
  return algorithmRegistry.listSupport()
}

export function validateSnapshotAlgorithmContract(
  snapshot: StudySessionSnapshot,
) {
  if (snapshot.storage_profile !== undefined && (
    snapshot.schema_version !== 'study-session.v4'
    || snapshot.storage_profile !== NOTE_STORAGE_PROFILE
  )) {
    throw new ClientAlgorithmContractError('Unsupported NOTE storage profile.')
  }
  const sessionAlgorithm = resolveClientAlgorithm(
    snapshot.scheduler_algorithm,
    snapshot.algorithm_version,
    'existing-lease',
  )

  for (const [policyKey, policy] of Object.entries(snapshot.policies)) {
    if (policy.config_hash !== policyKey) {
      throw new ClientAlgorithmContractError(
        `Scheduler policy ${policyKey} has an inconsistent config hash.`,
      )
    }
    if (
      policy.algorithm_key !== snapshot.scheduler_algorithm
      || policy.algorithm_version !== snapshot.algorithm_version
    ) {
      throw new ClientAlgorithmContractError(
        `Scheduler policy ${policyKey} does not match the session Algorithm.`,
      )
    }
    if (policy.config_schema_version !== sessionAlgorithm.configSchemaVersion) {
      throw new ClientAlgorithmContractError(
        `Scheduler policy ${policyKey} uses an unsupported config schema.`,
      )
    }
    if (policy.timezone !== snapshot.timezone) {
      throw new ClientAlgorithmContractError(
        `Scheduler policy ${policyKey} does not match the session timezone.`,
      )
    }
  }

  for (const card of snapshot.cards) {
    if (!snapshot.policies[card.policy_key]) {
      throw new ClientAlgorithmContractError(
        `Card ${card.card_id} references a missing scheduler policy.`,
      )
    }
  }

  return sessionAlgorithm
}

export function resolveCardAlgorithm(
  snapshot: StudySessionSnapshot,
  card: StudySessionCard,
) {
  const sessionAlgorithm = validateSnapshotAlgorithmContract(snapshot)
  const policy = snapshot.policies[card.policy_key]
  if (!policy) {
    throw new ClientAlgorithmContractError('Scheduler policy is missing.')
  }
  const algorithm = resolveClientAlgorithm(
    policy.algorithm_key,
    policy.algorithm_version,
    'existing-lease',
  )
  if (algorithm !== sessionAlgorithm) {
    throw new ClientAlgorithmContractError(
      `Card ${card.card_id} does not use the session Algorithm.`,
    )
  }
  return { algorithm, policy }
}

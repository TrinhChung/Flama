import type {
  StudySessionCard,
  StudySessionPolicy,
  StudySessionSnapshot,
} from '../types'
import { computeDecision } from './legacyEngine'
import type { SchedulerDecision } from './types'

export const LEGACY_ANKI_ALGORITHM = Object.freeze({
  key: 'legacy-anki',
  version: '1.0.0',
  stateSchemaVersion: 'anki-card-state.v1',
  configSchemaVersion: 'scheduler-config.v1',
})

export class ClientAlgorithmUnavailableError extends Error {
  readonly code = 'ALGORITHM_UNAVAILABLE'
  readonly algorithmKey: string
  readonly algorithmVersion: string

  constructor(algorithmKey: string, algorithmVersion: string) {
    super(
      `Study Algorithm ${algorithmKey}/${algorithmVersion} is unavailable in this client.`,
    )
    this.name = 'ClientAlgorithmUnavailableError'
    this.algorithmKey = algorithmKey
    this.algorithmVersion = algorithmVersion
  }
}

export class ClientAlgorithmContractError extends Error {
  readonly code = 'ALGORITHM_CONTRACT_MISMATCH'

  constructor(message: string) {
    super(message)
    this.name = 'ClientAlgorithmContractError'
  }
}

type ClientStudyAlgorithm = Readonly<{
  key: string
  version: string
  configSchemaVersion: string
  computeDecision: (
    card: StudySessionCard,
    policy: StudySessionPolicy,
    schedulerAtMs: number,
    timezone: string,
  ) => SchedulerDecision
}>

function registryKey(key: string, version: string) {
  return `${key}\u0000${version}`
}

const algorithms = new Map<string, ClientStudyAlgorithm>()

function registerClientAlgorithm(algorithm: ClientStudyAlgorithm) {
  const key = registryKey(algorithm.key, algorithm.version)
  if (algorithms.has(key)) {
    throw new Error(`Duplicate client Algorithm registration: ${key}`)
  }
  algorithms.set(key, Object.freeze(algorithm))
}

registerClientAlgorithm({
  key: LEGACY_ANKI_ALGORITHM.key,
  version: LEGACY_ANKI_ALGORITHM.version,
  configSchemaVersion: LEGACY_ANKI_ALGORITHM.configSchemaVersion,
  computeDecision: (card, policy, schedulerAtMs, timezone) => computeDecision(
    card.state,
    policy.config,
    schedulerAtMs,
    timezone,
  ),
})

export function resolveClientAlgorithm(key: string, version: string) {
  const normalizedKey = String(key || '').trim()
  const normalizedVersion = String(version || '').trim()
  const algorithm = algorithms.get(registryKey(normalizedKey, normalizedVersion))
  if (!algorithm) {
    throw new ClientAlgorithmUnavailableError(
      normalizedKey || '<missing>',
      normalizedVersion || '<missing>',
    )
  }
  return algorithm
}

export function validateSnapshotAlgorithmContract(
  snapshot: StudySessionSnapshot,
) {
  const sessionAlgorithm = resolveClientAlgorithm(
    snapshot.scheduler_algorithm,
    snapshot.algorithm_version,
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
  )
  if (algorithm !== sessionAlgorithm) {
    throw new ClientAlgorithmContractError(
      `Card ${card.card_id} does not use the session Algorithm.`,
    )
  }
  return { algorithm, policy }
}

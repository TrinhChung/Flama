import { describe, expect, it } from 'vitest'
import {
  ClientAlgorithmRegistry,
  ClientAlgorithmUnavailableError,
  getClientAlgorithmSupport,
  LEGACY_ANKI_ALGORITHM,
  listClientAlgorithmSupport,
} from './algorithmRegistry'
import type {
  AlgorithmLifecycleState,
  ClientAlgorithmIdentity,
  ClientStudyAlgorithm,
} from './algorithmRegistry'

function register(
  registry: ClientAlgorithmRegistry,
  version: string,
  lifecycleState: AlgorithmLifecycleState,
) {
  const identity: ClientAlgorithmIdentity = {
    key: 'algorithm',
    version,
    stateSchemaVersion: 'algorithm-state.v1',
    configSchemaVersion: 'algorithm-config.v1',
  }
  const algorithm: ClientStudyAlgorithm | null = lifecycleState === 'retired'
    ? null
    : {
        ...identity,
        computeDecision: () => {
          throw new Error('Lifecycle registry tests do not execute the evaluator.')
        },
      }
  registry.register(identity, { lifecycleState, algorithm })
  return algorithm
}

describe('client Algorithm lifecycle registry', () => {
  it('allows active and deprecated new sessions until lease-only cutoff', () => {
    const registry = new ClientAlgorithmRegistry()
    const active = register(registry, '1', 'active')
    const deprecated = register(registry, '2', 'deprecated')
    register(registry, '3', 'lease-only')

    expect(registry.resolve('algorithm', '1', 'new-session')).toBe(active)
    expect(registry.resolve('algorithm', '2', 'new-session')).toBe(deprecated)
    expect(() => registry.resolve('algorithm', '3', 'new-session'))
      .toThrowError(expect.objectContaining({
        code: 'ALGORITHM_UNAVAILABLE',
        purpose: 'new-session',
        lifecycleState: 'lease-only',
        reason: 'PURPOSE_NOT_SUPPORTED',
      }))
  })

  it('keeps lease-only evaluator available for admitted leases and jobs', () => {
    const registry = new ClientAlgorithmRegistry()
    const evaluator = register(registry, '1', 'lease-only')

    expect(registry.resolve('algorithm', '1', 'existing-lease')).toBe(evaluator)
    expect(registry.resolve('algorithm', '1', 'accepted-job')).toBe(evaluator)
  })

  it('retains history metadata independently from executable replay', () => {
    const registry = new ClientAlgorithmRegistry()
    register(registry, '1', 'retired')

    expect(registry.support('algorithm', '1')).toMatchObject({
      lifecycleState: 'retired',
      clientEvaluator: false,
      existingLeaseAllowed: false,
      historyReadAllowed: true,
    })
    expect(() => registry.resolve('algorithm', '1', 'existing-lease'))
      .toThrowError(expect.objectContaining({
        code: 'ALGORITHM_UNAVAILABLE',
        reason: 'RETIRED',
      }))
  })

  it('never falls forward from an unknown exact version', () => {
    const registry = new ClientAlgorithmRegistry()
    register(registry, '2', 'active')

    expect(() => registry.resolve('algorithm', '1', 'existing-lease'))
      .toThrow(ClientAlgorithmUnavailableError)
    try {
      registry.resolve('algorithm', '1', 'existing-lease')
    } catch (error) {
      expect(error).toMatchObject({
        reason: 'UNKNOWN_VERSION',
        lifecycleState: null,
      })
    }
  })

  it('returns deterministic support introspection', () => {
    const registry = new ClientAlgorithmRegistry()
    register(registry, '2', 'lease-only')
    register(registry, '1', 'active')

    expect(registry.listSupport().map(({ identity }) => identity.version))
      .toEqual(['1', '2'])
    expect(registry.listSupport()[1]).toMatchObject({
      newSessionAllowed: false,
      existingLeaseAllowed: true,
      acceptedJobAllowed: true,
    })
  })

  it('keeps the production default active and decoder-aware', () => {
    expect(getClientAlgorithmSupport(
      LEGACY_ANKI_ALGORITHM.key,
      LEGACY_ANKI_ALGORITHM.version,
    )).toMatchObject({
      lifecycleState: 'active',
      clientEvaluator: true,
      newSessionAllowed: true,
      artifacts: {
        stateDecoder: true,
        configDecoder: true,
        eventHistoryDecoder: true,
        interactionContractDecoder: true,
      },
    })
    expect(listClientAlgorithmSupport()).toHaveLength(1)
  })
})

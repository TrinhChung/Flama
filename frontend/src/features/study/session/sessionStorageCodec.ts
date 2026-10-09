import type { StudySessionCard, StudySessionSnapshot } from '../types'
import type { PersistedStudySession } from './sessionStore'

const STORAGE_SCHEMA = 'study-session-storage.v1'
type ArtifactMaps = Pick<StudySessionSnapshot, 'contents' | 'templates' | 'policies' | 'compositions'>

export type StoredSessionArtifacts = ArtifactMaps & {
  id: string
  scope_key: string
  session_id: string
  cards: StudySessionCard[]
}

export type StoredSessionCheckpoint = Omit<PersistedStudySession, 'snapshot'> & {
  storage_schema: typeof STORAGE_SCHEMA
  artifact_key: string
  snapshot: Omit<StudySessionSnapshot, keyof ArtifactMaps | 'cards'>
  card_overrides: Array<[number, StudySessionCard]>
}

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function artifactKeyForCheckpoint(value: unknown): string | null {
  return record(value) && value.storage_schema === STORAGE_SCHEMA && typeof value.artifact_key === 'string'
    ? value.artifact_key : null
}

/** Content patches replace the maps; rating, undo and batch changes retain them. */
export function hasSameArtifactMaps(artifacts: StoredSessionArtifacts, session: PersistedStudySession) {
  const snapshot = session.snapshot
  return artifacts.scope_key === session.scope_key
    && artifacts.session_id === snapshot.session_id
    && artifacts.contents === snapshot.contents
    && artifacts.templates === snapshot.templates
    && artifacts.policies === snapshot.policies
    && artifacts.compositions === snapshot.compositions
    && artifacts.cards.length === snapshot.cards.length
    && artifacts.cards.every((card, index) => card.card_id === snapshot.cards[index].card_id)
}

export function splitSessionCheckpoint(session: PersistedStudySession, previous?: StoredSessionArtifacts) {
  const { contents, templates, policies, compositions, cards, ...snapshot } = session.snapshot
  const artifacts: StoredSessionArtifacts = previous && hasSameArtifactMaps(previous, session)
    ? previous
    : { id: crypto.randomUUID(), scope_key: session.scope_key, session_id: snapshot.session_id,
        contents, templates, policies, compositions, cards }
  const cardOverrides: Array<[number, StudySessionCard]> = []
  cards.forEach((card, index) => {
    if (card !== artifacts.cards[index]) cardOverrides.push([index, card])
  })
  const checkpoint: StoredSessionCheckpoint = {
    ...session, snapshot, storage_schema: STORAGE_SCHEMA, artifact_key: artifacts.id, card_overrides: cardOverrides,
  }
  return { checkpoint, artifacts }
}

/** Leave malformed evidence intact so the existing validator quarantines it. */
export function hydrateStoredCheckpoint(checkpoint: unknown, artifacts: unknown): unknown {
  const key = artifactKeyForCheckpoint(checkpoint)
  if (!key || !record(checkpoint) || !record(checkpoint.snapshot) || !record(artifacts)
    || artifacts.id !== key || artifacts.scope_key !== checkpoint.scope_key
    || artifacts.session_id !== checkpoint.snapshot.session_id
    || !record(artifacts.contents) || !record(artifacts.templates)
    || !record(artifacts.policies) || !record(artifacts.compositions)
    || !Array.isArray(artifacts.cards) || !Array.isArray(checkpoint.card_overrides)) return checkpoint
  const cards = [...artifacts.cards]
  const seen = new Set<number>()
  for (const override of checkpoint.card_overrides) {
    if (!Array.isArray(override) || override.length !== 2 || !Number.isInteger(override[0])
      || override[0] < 0 || override[0] >= cards.length || seen.has(override[0])
      || !record(override[1]) || !record(cards[override[0]])
      || override[1].card_id !== (cards[override[0]] as Record<string, unknown>).card_id) return checkpoint
    seen.add(override[0])
    cards[override[0]] = override[1]
  }
  return { ...checkpoint, snapshot: { ...checkpoint.snapshot,
    cards,
    contents: artifacts.contents, templates: artifacts.templates,
    policies: artifacts.policies, compositions: artifacts.compositions,
  } }
}

export function artifactsForRestoredSession(session: PersistedStudySession, id: string, cards: StudySessionCard[]): StoredSessionArtifacts {
  const { contents, templates, policies, compositions } = session.snapshot
  return { id, scope_key: session.scope_key, session_id: session.snapshot.session_id,
    contents, templates, policies, compositions, cards }
}

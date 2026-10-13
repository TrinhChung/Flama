import type { CardMediaArtifact } from './types'

export interface CardContentUpdate {
  cardId: string
  noteId?: string | null
  fieldValues: Record<string, unknown>
  media?: CardMediaArtifact[]
}

type CardContentUpdater = (update: CardContentUpdate) => Promise<void>
let contentUpdater: CardContentUpdater | undefined

/** The application binds persistence; the entity does not own study sessions. */
export function configureCardContentUpdater(updater: CardContentUpdater): () => void {
  const previous = contentUpdater
  contentUpdater = updater
  return () => {
    if (contentUpdater === updater) contentUpdater = previous
  }
}

/** Resolves after persisted sessions have been patched and listeners notified. */
export async function updateCardFieldValues(update: CardContentUpdate): Promise<void> {
  if (!contentUpdater) throw new Error('Card content persistence is not configured')
  await contentUpdater(update)
}

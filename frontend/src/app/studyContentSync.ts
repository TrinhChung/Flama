import { configureCardContentUpdater } from '@/entities/flashcard/model/cardContentUpdates'

// Register before routes render. Load headless storage only when a card changes;
// opening Browse or Audio does not require mounting Study or loading its page.
configureCardContentUpdater(async ({ cardId, fieldValues, noteId, media }) => {
  const { updateCardFieldValuesInSessions } = await import('@/features/study/contentUpdates')
  await updateCardFieldValuesInSessions(cardId, fieldValues, { noteId, media })
})

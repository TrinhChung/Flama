import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import type { useBrowseState } from '@/features/browse'

export function useBrowseWorkspaceActions(browse: ReturnType<typeof useBrowseState>) {
  const { t } = useTranslation('browse')
  const { selectedCards } = browse
  const openWorksheetModal = () => {
    if (selectedCards.length === 0) {
      if (!browse.selectedDeckId && !browse.cardsQuery.data?.items[0]?.deck_id) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (browse.selectedDeck?.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    const firstDeckId = browse.cardsQuery.data?.items[0]?.deck_id
    const targetDeckId = browse.selectedDeckId || firstDeckId || 1
    browse.setWorksheetTargetDeckId(targetDeckId)
    browse.setWorksheetTargetCardIds(selectedCards.length > 0 ? selectedCards : undefined)
    browse.setIsWorksheetModalOpen(true)
  }

  const openBatchStrokeModal = () => {
    if (selectedCards.length === 0) {
      if (!browse.selectedDeckId) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (browse.selectedDeck?.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    browse.setStrokeModalMode('batch')
    browse.setIsStrokeModalOpen(true)
  }

  const worksheetTitle = selectedCards.length === 0
    ? browse.selectedDeck
      ? t('header.worksheet_deck_tooltip', {
          name: browse.selectedDeck.name,
          count: browse.selectedDeck.counts?.total ?? 0,
        })
      : t('header.worksheet_generic_tooltip')
    : t('header.worksheet_selected_tooltip', { count: selectedCards.length })

  const strokeTitle = selectedCards.length === 0 && browse.selectedDeck
    ? t('header.svg_stroke_deck_tooltip', {
        name: browse.selectedDeck.name,
        count: browse.selectedDeck.counts?.total ?? 0,
      })
    : undefined

  return { openWorksheetModal, openBatchStrokeModal, worksheetTitle, strokeTitle }
}

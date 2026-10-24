import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { browseApi } from '../api/browseApi'
import type { useBrowseData } from './useBrowseData'
import type { useBrowseEditor } from './useBrowseEditor'
import type { useBrowseSelection } from './useBrowseSelection'

type BrowseBatchOptions = {
  data: ReturnType<typeof useBrowseData>
  editor: ReturnType<typeof useBrowseEditor>
  selection: ReturnType<typeof useBrowseSelection>
}

export function useBrowseBatchActions({ data, editor, selection }: BrowseBatchOptions) {
  const { t } = useTranslation('browse')
  const queryClient = useQueryClient()
  const { cards } = data
  const { cardDetailQuery, setActiveCardId } = editor
  const { setSelectedCards, selectedNoteIdsRef } = selection
  // Single Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: async (cardId: string) => {
      const detail = cardDetailQuery.data
      const noteId = cards.find((row) => row.card_id === cardId)?.note_id
        ?? (detail?.card.card_id === cardId ? detail.note.id : undefined)
      if (!noteId) throw new Error(t('toasts.delete_error'))
      await browseApi.deleteNote(noteId)
      return cardId
    },
    onSuccess: (cardId) => {
      toast.success(t('toasts.delete_success'))
      setActiveCardId((current) => current === cardId ? null : current)
      setSelectedCards((current) => current.filter((id) => id !== cardId))
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'decks'] })
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
    },
    onError: (error: Error) => {
      toast.error(t('toasts.delete_error'), { description: error.message })
    },
  })

  // Bulk Delete Mutation
  const bulkDeleteMutation = useMutation({
    mutationFn: async (cardIds: string[]) => {
      const noteIds = [...new Set(cardIds.map((cardId) => {
        const noteId = cards.find((row) => row.card_id === cardId)?.note_id
          ?? selectedNoteIdsRef.current.get(cardId)
        if (!noteId) throw new Error(t('toasts.bulk_delete_error'))
        return noteId
      }))]
      const res = await browseApi.deleteNotes(noteIds)
      return { count: res.deleted_count ?? noteIds.length, cardIds }
    },
    onMutate: () => {
      toast?.loading?.(t('toasts.bulk_deleting'), {
        id: 'bulk-delete-cards',
        description: t('toasts.bulk_deleting_desc'),
      })
    },
    onSuccess: ({ count, cardIds }) => {
      toast.success(t('toasts.bulk_delete_success', { count }), { id: 'bulk-delete-cards' })
      const deleted = new Set(cardIds)
      setActiveCardId((current) => current && deleted.has(current) ? null : current)
      setSelectedCards((current) => current.filter((id) => !deleted.has(id)))
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'decks'] })
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
    },
    onError: (error: Error) => {
      toast.error(t('toasts.bulk_delete_error'), { id: 'bulk-delete-cards', description: error.message })
    },
  })


  return { deleteMutation, bulkDeleteMutation }
}

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { createNoteType, fetchNoteTypeSummaries, noteTypeManagerQueryKey } from '../api/noteTypeManagerApi'

const TOUR_STORAGE_KEY = 'flama_notetype_spotlight_tour_v1'

export function useNoteTypeManager() {
  const { t } = useTranslation('note_types')
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const [name, setName] = useState('')
  const [tourOpen, setTourOpen] = useState(false)

  const query = useQuery({
    queryKey: noteTypeManagerQueryKey,
    queryFn: ({ signal }) => fetchNoteTypeSummaries(signal),
  })
  const noteTypes = query.data?.items || []

  useEffect(() => {
    if (query.isSuccess) {
      const completed = localStorage.getItem(TOUR_STORAGE_KEY)
      if (!completed && noteTypes.length === 0) {
        const timer = setTimeout(() => setTourOpen(true), 500)
        return () => clearTimeout(timer)
      }
    }
  }, [query.isSuccess, noteTypes.length])

  const closeTour = () => {
    localStorage.setItem(TOUR_STORAGE_KEY, 'true')
    setTourOpen(false)
  }

  const createMutation = useMutation({
    mutationFn: createNoteType,
    onSuccess: (data) => {
      toast.success(t('manager.messages.create_success'))
      setName('')
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
      navigate(`/flashcards/note-types/${data.id}/fields`)
    },
    onError: (error: Error) => {
      toast.error(t('manager.messages.create_error'), { description: error.message })
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error(t('manager.messages.name_required'))
      return
    }
    createMutation.mutate(trimmed)
  }

  return {
    query,
    noteTypes,
    name,
    setName,
    tourOpen,
    setTourOpen,
    closeTour,
    createMutation,
    handleCreate,
  }
}

import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'

export type NoteTypeItem = {
  id: string
  name: string
  field_defs?: Array<{ id: string; name: string }>
  templates?: Array<{ id: string; name: string }>
  publish_status?: string
  created_at?: string
  updated_at?: string
}

export type NoteTypesResponse = {
  items: NoteTypeItem[]
}

export function useNoteTypeManager() {
  const { t } = useTranslation('note_types')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  const [name, setName] = useState('')
  const [noteTypeToDelete, setNoteTypeToDelete] = useState<NoteTypeItem | null>(null)
  const [purgeNoteType, setPurgeNoteType] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)

  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<NoteTypesResponse>('/note-types'),
  })

  const createMutation = useMutation({
    mutationFn: (newTypeName: string) =>
      appApi.mutate<NoteTypeItem>('/note-types', 'POST', { name: newTypeName }),
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

  const deleteMutation = useMutation<unknown, Error, { id: string; purge?: boolean }>({
    mutationFn: ({ id, purge }) => {
      const suffix = purge ? '?purge=true' : ''
      return appApi.mutate(`/note-types/${id}${suffix}`, 'DELETE')
    },
    onSuccess: () => {
      toast.success(t('manager.messages.delete_success'))
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
      setNoteTypeToDelete(null)
      setPurgeNoteType(false)
    },
    onError: (error: Error) => {
      toast.error(t('manager.messages.delete_error'), { description: error.message })
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
    noteTypes: query.data?.items || [],
    isAdmin,
    name,
    setName,
    noteTypeToDelete,
    setNoteTypeToDelete,
    purgeNoteType,
    setPurgeNoteType,
    tourOpen,
    setTourOpen,
    createMutation,
    deleteMutation,
    handleCreate,
  }
}

import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'

export type FieldDefItem = {
  id: string
  name: string
  field_type: string
  required: boolean
  position: number
  identity_role: 'primary' | null
}

export type NoteTypeDetail = {
  id: string
  name: string
  field_defs?: FieldDefItem[]
}

export const FIELD_TYPES = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram']

export function useNoteTypeFields() {
  const { t } = useTranslation('note_types')
  const { id: noteTypeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [isAddingField, setIsAddingField] = useState(false)

  // Edit Field State
  const [editName, setEditName] = useState('')
  const [editType, setEditType] = useState('text')
  const [editRequired, setEditRequired] = useState(false)
  const [editIdentity, setEditIdentity] = useState(false)

  // New Field State
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('text')

  // Drag & Drop State
  const [draggedId, setDraggedId] = useState<string | null>(null)

  const editFormRef = useRef<HTMLDivElement>(null)
  const scrollToFormOnMobile = () => {
    if (typeof window !== 'undefined' && window.innerWidth < 768 && editFormRef.current) {
      setTimeout(() => {
        editFormRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }, 50)
    }
  }

  const query = useQuery({
    queryKey: ['note-type-fields', noteTypeId],
    queryFn: () => appApi.get<{ items: FieldDefItem[] }>(`/note-types/${noteTypeId}/fields`),
    enabled: Boolean(noteTypeId),
  })

  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => appApi.get<NoteTypeDetail>(`/note-types/${noteTypeId}`),
    enabled: Boolean(noteTypeId),
  })

  const fields = (query.data?.items || []).slice().sort((a, b) => a.position - b.position)
  const selectedField = fields.find((f) => f.id === selectedFieldId) || null

  // Auto-select first field when data loads if none selected
  useEffect(() => {
    if (fields.length && !selectedFieldId && !isAddingField) {
      setSelectedFieldId(fields[0].id)
    }
  }, [fields, selectedFieldId, isAddingField])

  // Sync edit form when selected field changes
  useEffect(() => {
    if (selectedField) {
      setEditName(selectedField.name)
      setEditType(selectedField.field_type)
      setEditRequired(selectedField.required)
      setEditIdentity(selectedField.identity_role === 'primary')
    }
  }, [selectedField])

  // Create Field Mutation
  const createMutation = useMutation({
    mutationFn: (payload: { name: string; field_type: string; required: boolean; identity_role: 'primary' | null }) =>
      appApi.mutate<FieldDefItem>(`/note-types/${noteTypeId}/fields`, 'POST', payload),
    onSuccess: (newField) => {
      toast.success(t('fields.messages.create_success'))
      setIsAddingField(false)
      setSelectedFieldId(newField.id)
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error(t('fields.messages.create_error'), { description: error.message })
    },
  })

  // Patch Field Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { name: string; field_type: string; required: boolean; identity_role: 'primary' | null }) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/${selectedFieldId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success(t('fields.messages.update_success'))
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error(t('fields.messages.update_error'), { description: error.message })
    },
  })

  // Delete Field Mutation
  const deleteMutation = useMutation({
    mutationFn: (fieldId: string) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/${fieldId}`, 'DELETE'),
    onSuccess: () => {
      toast.success(t('fields.messages.delete_success'))
      setSelectedFieldId(null)
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error(t('fields.messages.delete_error'), { description: error.message })
    },
  })

  // Reorder Mutation
  const reorderMutation = useMutation({
    mutationFn: (payload: Array<{ id: string; position: number }>) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/reorder`, 'POST', payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error(t('fields.messages.reorder_error'), { description: error.message })
    },
  })

  const handleDragStart = (id: string) => {
    setDraggedId(id)
  }

  const handleDrop = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return
    const draggedIndex = fields.findIndex((f) => f.id === draggedId)
    const targetIndex = fields.findIndex((f) => f.id === targetId)
    if (draggedIndex < 0 || targetIndex < 0) return

    const reordered = [...fields]
    const [item] = reordered.splice(draggedIndex, 1)
    reordered.splice(targetIndex, 0, item)

    const payload = reordered.map((f, idx) => ({ id: f.id, position: idx }))
    setDraggedId(null)
    reorderMutation.mutate(payload)
  }

  const handleMoveUp = (index: number) => {
    if (index <= 0) return
    const reordered = [...fields]
    const [item] = reordered.splice(index, 1)
    reordered.splice(index - 1, 0, item)
    const payload = reordered.map((f, idx) => ({ id: f.id, position: idx }))
    reorderMutation.mutate(payload)
  }

  const handleMoveDown = (index: number) => {
    if (index >= fields.length - 1) return
    const reordered = [...fields]
    const [item] = reordered.splice(index, 1)
    reordered.splice(index + 1, 0, item)
    const payload = reordered.map((f, idx) => ({ id: f.id, position: idx }))
    reorderMutation.mutate(payload)
  }

  return {
    noteTypeId,
    query,
    detailQuery,
    fields,
    selectedField,
    selectedFieldId,
    setSelectedFieldId,
    isAddingField,
    setIsAddingField,
    editName,
    setEditName,
    editType,
    setEditType,
    editRequired,
    setEditRequired,
    editIdentity,
    setEditIdentity,
    newName,
    setNewName,
    newType,
    setNewType,
    editFormRef,
    scrollToFormOnMobile,
    createMutation,
    updateMutation,
    deleteMutation,
    reorderMutation,
    handleDragStart,
    handleDrop,
    handleMoveUp,
    handleMoveDown,
  }
}

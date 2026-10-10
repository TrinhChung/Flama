import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { cardTemplateQueryKeys } from '@/entities/card-template'

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
  publish_status?: string
  field_defs?: FieldDefItem[]
}

export const FIELD_TYPES = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram', 'answers'] as const
type FieldWrite = Pick<FieldDefItem, 'name' | 'field_type' | 'required' | 'identity_role'>
type FieldsApi = {
  get: <T>(path: string) => Promise<T>
  mutate: <T>(path: string, method: 'POST' | 'PATCH' | 'DELETE', payload?: unknown) => Promise<T>
}

/** A field draft belongs to its ID; background refetches cannot overwrite edits. */
export function useNoteTypeFields(api: FieldsApi) {
  const { t } = useTranslation('note_types')
  const { id: noteTypeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const routeId = useRef(noteTypeId)
  routeId.current = noteTypeId
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [isAddingField, setIsAddingField] = useState(false)
  const [baseline, setBaseline] = useState<FieldDefItem | null>(null)
  const [editName, setEditName] = useState('')
  const [editType, setEditType] = useState('text')
  const [editRequired, setEditRequired] = useState(false)
  const [editIdentity, setEditIdentity] = useState(false)
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('text')
  const [newRequired, setNewRequired] = useState(false)
  const [newIdentity, setNewIdentity] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [orderDraft, setOrderDraft] = useState<string[] | null>(null)

  const query = useQuery({
    queryKey: ['note-type-fields', noteTypeId],
    queryFn: () => api.get<{ items: FieldDefItem[] }>(`/note-types/${encodeURIComponent(noteTypeId!)}/fields`),
    enabled: Boolean(noteTypeId),
  })
  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => api.get<NoteTypeDetail>(`/note-types/${encodeURIComponent(noteTypeId!)}`),
    enabled: Boolean(noteTypeId),
  })
  const serverFields = useMemo(() => (query.data?.items ?? []).slice().sort((a, b) => a.position - b.position), [query.data])
  const isOrderDirty = useMemo(() => {
    if (!orderDraft || orderDraft.length !== serverFields.length) return false
    return orderDraft.some((id, idx) => id !== serverFields[idx]?.id)
  }, [orderDraft, serverFields])
  const fields = useMemo(() => {
    if (!orderDraft) return serverFields
    const map = new Map(serverFields.map((f) => [f.id, f]))
    const result: FieldDefItem[] = []
    for (const id of orderDraft) {
      const f = map.get(id)
      if (f) result.push(f)
    }
    for (const f of serverFields) {
      if (!result.includes(f)) result.push(f)
    }
    return result
  }, [orderDraft, serverFields])
  const serverField = fields.find((field) => field.id === selectedFieldId) ?? null
  const selectedField = serverField ?? (baseline?.id === selectedFieldId ? baseline : null)
  const isDirty = isAddingField
    ? Boolean(newName || newType !== 'text' || newRequired || newIdentity)
    : Boolean(baseline && (editName !== baseline.name || editType !== baseline.field_type ||
      editRequired !== baseline.required || editIdentity !== (baseline.identity_role === 'primary')))
  const dirtyRef = useRef(isDirty)
  dirtyRef.current = isDirty

  const loadField = (field: FieldDefItem | null) => {
    setBaseline(field)
    setEditName(field?.name ?? '')
    setEditType(field?.field_type ?? 'text')
    setEditRequired(Boolean(field?.required))
    setEditIdentity(field?.identity_role === 'primary')
    setFormError(null)
  }
  const resetNewField = () => {
    setNewName('')
    setNewType('text')
    setNewRequired(false)
    setNewIdentity(false)
    setFormError(null)
  }
  useEffect(() => {
    setSelectedFieldId(null)
    setIsAddingField(false)
    loadField(null)
    resetNewField()
    setDraggedId(null)
    setOrderDraft(null)
  }, [noteTypeId])
  useEffect(() => {
    if (!isAddingField && !selectedFieldId && fields.length) setSelectedFieldId(fields[0].id)
  }, [fields, selectedFieldId, isAddingField])
  useEffect(() => {
    if (isAddingField) return
    if (serverField && (baseline?.id !== selectedFieldId || !dirtyRef.current)) loadField(serverField)
    else if (!serverField && baseline?.id === selectedFieldId && !dirtyRef.current && query.isSuccess) {
      loadField(null)
      setSelectedFieldId(null)
    }
  }, [serverField, selectedFieldId, isAddingField, query.isSuccess, baseline?.id])

  const invalidateFields = (id: string) => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['note-type-fields', id] }),
    queryClient.invalidateQueries({ queryKey: ['note-type-detail', id] }),
    queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.applications(id).slice(0, 3) }),
    queryClient.invalidateQueries({ queryKey: cardTemplateQueryKeys.noteTypeTemplates(id) }),
  ])
  const createMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: FieldWrite }) =>
      api.mutate<FieldDefItem>(`/note-types/${encodeURIComponent(id)}/fields`, 'POST', payload),
    onSuccess: async (field, { id }) => {
      queryClient.setQueryData<{ items: FieldDefItem[] }>(['note-type-fields', id], (old) => ({ items: [...(old?.items ?? []), field] }))
      if (routeId.current === id) {
        setIsAddingField(false)
        resetNewField()
        setSelectedFieldId(field.id)
        loadField(field)
      }
      toast.success(t('fields.messages.create_success'))
      await invalidateFields(id)
    },
    onError: (error: Error) => { setFormError(error.message); toast.error(t('fields.messages.create_error'), { description: error.message }) },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, fieldId, payload }: { id: string; fieldId: string; payload: FieldWrite }) =>
      api.mutate<{ field: FieldDefItem }>(`/note-types/${encodeURIComponent(id)}/fields/${encodeURIComponent(fieldId)}`, 'PATCH', payload),
    onSuccess: async (result, { id, fieldId }) => {
      const field = result.field
      queryClient.setQueryData<{ items: FieldDefItem[] }>(['note-type-fields', id], (old) => old && ({ items: old.items.map((item) => item.id === fieldId ? field : item) }))
      if (routeId.current === id && selectedFieldId === fieldId) loadField(field)
      toast.success(t('fields.messages.update_success'))
      await invalidateFields(id)
    },
    onError: (error: Error) => { setFormError(error.message); toast.error(t('fields.messages.update_error'), { description: error.message }) },
  })
  const deleteMutation = useMutation({
    mutationFn: ({ id, fieldId }: { id: string; fieldId: string }) =>
      api.mutate(`/note-types/${encodeURIComponent(id)}/fields/${encodeURIComponent(fieldId)}`, 'DELETE'),
    onSuccess: async (_result, { id, fieldId }) => {
      queryClient.setQueryData<{ items: FieldDefItem[] }>(['note-type-fields', id], (old) => old && ({ items: old.items.filter((field) => field.id !== fieldId) }))
      if (routeId.current === id) { loadField(null); setSelectedFieldId(null) }
      toast.success(t('fields.messages.delete_success'))
      await invalidateFields(id)
    },
    onError: (error: Error) => { setFormError(error.message); toast.error(t('fields.messages.delete_error'), { description: error.message }) },
  })
  const reorderMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Array<{ id: string; position: number }> }) =>
      api.mutate(`/note-types/${encodeURIComponent(id)}/fields/reorder`, 'POST', payload),
    onSuccess: async (_result, { id }) => {
      setOrderDraft(null)
      await invalidateFields(id)
    },
    onError: (error: Error) => toast.error(t('fields.messages.reorder_error'), { description: error.message }),
  })
  const isBusy = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending || reorderMutation.isPending

  const saveDraft = async () => {
    if (!noteTypeId) return
    if (isBusy) throw new Error(t('setup.operation_pending'))
    const name = (isAddingField ? newName : editName).trim()
    if (!name) {
      const message = t('fields.messages.name_required')
      setFormError(message)
      throw new Error(message)
    }
    const identity = isAddingField ? newIdentity : editIdentity
    const payload: FieldWrite = {
      name,
      field_type: identity ? 'text' : (isAddingField ? newType : editType),
      required: identity || (isAddingField ? newRequired : editRequired),
      identity_role: identity ? 'primary' : null,
    }
    setFormError(null)
    if (isAddingField) await createMutation.mutateAsync({ id: noteTypeId, payload })
    else if (selectedFieldId) await updateMutation.mutateAsync({ id: noteTypeId, fieldId: selectedFieldId, payload })
  }
  const discardDraft = () => { if (isAddingField) resetNewField(); else loadField(serverField ?? baseline) }
  const selectField = (id: string) => { setIsAddingField(false); setSelectedFieldId(id); loadField(fields.find((field) => field.id === id) ?? null) }
  const startAddField = () => { resetNewField(); setIsAddingField(true); setSelectedFieldId(null); loadField(null) }
  const cancelAddField = () => { resetNewField(); setIsAddingField(false); setSelectedFieldId(fields[0]?.id ?? null); loadField(fields[0] ?? null) }
  const reorder = (from: number, to: number) => {
    if (!noteTypeId || isBusy || from < 0 || to < 0 || to >= fields.length || from === to) return
    const reorderedIds = fields.map((f) => f.id)
    const [movedId] = reorderedIds.splice(from, 1)
    reorderedIds.splice(to, 0, movedId)
    const isSameAsServer = reorderedIds.length === serverFields.length &&
      reorderedIds.every((id, idx) => id === serverFields[idx]?.id)
    setOrderDraft(isSameAsServer ? null : reorderedIds)
  }
  const saveOrder = async () => {
    if (!noteTypeId || isBusy || !isOrderDirty) return
    const payload = fields.map((item, position) => ({ id: item.id, position }))
    await reorderMutation.mutateAsync({ id: noteTypeId, payload })
    setOrderDraft(null)
    toast.success(t('fields.messages.reorder_success'))
  }
  const discardOrder = () => {
    setOrderDraft(null)
  }
  const saveAll = async () => {
    if (!noteTypeId || isBusy) return
    if (isDirty) await saveDraft()
    if (isOrderDirty) await saveOrder()
  }

  return {
    noteTypeId, query, detailQuery, fields, selectedField, selectedFieldId, isAddingField,
    editName, setEditName, editType, setEditType, editRequired, setEditRequired, editIdentity, setEditIdentity,
    newName, setNewName, newType, setNewType, newRequired, setNewRequired, newIdentity, setNewIdentity,
    formError, isDirty, isOrderDirty, canSave: isDirty || isOrderDirty, isBusy,
    saveDraft, discardDraft, saveOrder, discardOrder, saveAll, selectField, startAddField, cancelAddField,
    createMutation, updateMutation, deleteMutation, reorderMutation,
    /** Refetch fields after a change made outside this editor (e.g. the answers conversion). */
    refreshFields: () => (noteTypeId ? invalidateFields(noteTypeId) : Promise.resolve()),
    handleDragStart: (id: string) => setDraggedId(id),
    handleDrop: (targetId: string) => {
      reorder(fields.findIndex((field) => field.id === draggedId), fields.findIndex((field) => field.id === targetId))
      setDraggedId(null)
    },
    handleMoveUp: (index: number) => reorder(index, index - 1),
    handleMoveDown: (index: number) => reorder(index, index + 1),
  }
}

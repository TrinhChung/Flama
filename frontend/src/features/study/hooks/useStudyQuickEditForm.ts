import '@/shared/config/i18n'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { resolveBackendUrl } from '@/config/env'
import { fieldValueEditorText, serializeArrayFieldValues } from '@/lib/arrayField'
import { noteWritePreconditions } from '@/lib/noteWritePreconditions'
import type { StudyContentArtifact, StudyMediaArtifact, StudyTemplateArtifact } from '../types'
import type { CardDetailResponse as BrowseCardDetailResponse } from '@/features/browse/types'

/** The Browse card detail; `decks` is read here although the Browse API does not send it today. */
type CardDetailResponse = BrowseCardDetailResponse & {
  decks?: Array<{ id: number; name: string; path?: string }>
}

export type UpdateCardResponse = {
  success: boolean
  row?: unknown
  detail?: CardDetailResponse
}

export function inferFieldType(
  rawFieldType?: unknown,
  fieldName?: unknown,
  fieldValue?: unknown,
): 'image' | 'audio' | 'diagram' | 'text' | 'array' {
  const ft = typeof rawFieldType === 'string' ? rawFieldType.trim().toLowerCase() : ''
  if (ft === 'image' || ft === 'audio' || ft === 'diagram' || ft === 'array') {
    return ft
  }

  const name = typeof fieldName === 'string' ? fieldName.trim().toLowerCase() : ''
  if (
    name === 'audio' ||
    name === 'sound' ||
    name === 'voice' ||
    name.endsWith('_audio') ||
    name.endsWith(' audio') ||
    name.endsWith('_sound') ||
    name.endsWith(' sound')
  ) {
    return 'audio'
  }

  if (
    name === 'image' ||
    name === 'picture' ||
    name === 'photo' ||
    name === 'diagram' ||
    name === 'illustration' ||
    name.endsWith('_image') ||
    name.endsWith(' image') ||
    name.endsWith('_photo') ||
    name.endsWith(' photo') ||
    name.endsWith('_picture') ||
    name.endsWith(' picture')
  ) {
    return 'image'
  }

  if (Array.isArray(fieldValue)) {
    return 'array'
  }

  const val =
    typeof fieldValue === 'string'
      ? fieldValue.trim()
      : fieldValue == null
      ? ''
      : fieldValueEditorText(fieldValue).trim()

  if (val.startsWith('[sound:') || /\.(mp3|wav|ogg|opus|m4a|aac|flac)(\?.*)?$/i.test(val)) {
    return 'audio'
  }
  if (/\.(png|jpe?g|webp|gif|svg|avif)(\?.*)?$/i.test(val)) {
    return 'image'
  }

  return 'text'
}

export type UseStudyQuickEditFormOptions = {
  open: boolean
  cardId?: string | null
  template?: StudyTemplateArtifact | null
  content?: StudyContentArtifact | null
  onCardUpdated: (
    cardId: string,
    newFieldValues: Record<string, unknown>,
    options?: { media?: StudyMediaArtifact[]; noteId?: string | null },
  ) => void | Promise<void>
  onClose: () => void
}

export function useStudyQuickEditForm({
  open,
  cardId,
  template,
  content,
  onCardUpdated,
  onClose,
}: UseStudyQuickEditFormOptions) {
  const { t } = useTranslation('study')
  const queryClient = useQueryClient()

  const [fieldValues, setFieldValues] = useState<Record<string, unknown>>({})
  const [initialFieldValues, setInitialFieldValues] = useState<Record<string, unknown>>({})
  const [invalidArrayFields, setInvalidArrayFields] = useState<Record<string, boolean>>({})
  const handleFieldValidityChange = useCallback((name: string, valid: boolean) => {
    setInvalidArrayFields((previous) => previous[name] === !valid ? previous : { ...previous, [name]: !valid })
  }, [])
  const [tags, setTags] = useState<string[]>([])
  const [initialTags, setInitialTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [deckId, setDeckId] = useState<number | null>(null)
  const [initialDeckId, setInitialDeckId] = useState<number | null>(null)

  const isFormInitializedRef = useRef(false)
  const initialWritePreconditionsRef = useRef<ReturnType<typeof noteWritePreconditions>>({})
  const hydratedDetailRef = useRef<CardDetailResponse | null>(null)
  const initialDetailConflictRef = useRef(false)

  // Query background card detail for full deck tree options and tags
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', cardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${cardId}`),
    enabled: Boolean(open && cardId),
  })

  // Initialize immediately from available study session content (0ms latency)
  useEffect(() => {
    if (open && content && !isFormInitializedRef.current) {
      const projection = template?.binding_projection
      const baseValues = projection
        ? Object.fromEntries(projection.field_defs
          .filter((field) => Object.hasOwn(content.field_values, field.name)
            && (!Object.hasOwn(projection.input_bindings, field.name)
              || projection.input_bindings[field.name] === field.id))
          .map((field) => [field.name, content.field_values[field.name]]))
        : { ...(content.field_values || {}) }
      setFieldValues(baseValues)
      setInitialFieldValues(baseValues)
      isFormInitializedRef.current = true
    } else if (!open) {
      isFormInitializedRef.current = false
      setFieldValues({})
      setInitialFieldValues({})
      setTags([])
      setInitialTags([])
      setDeckId(null)
      setInitialDeckId(null)
      setNewTagInput('')
      setInvalidArrayFields({})
      initialWritePreconditionsRef.current = {}
      hydratedDetailRef.current = null
      initialDetailConflictRef.current = false
    }
  }, [open, content, template?.binding_projection])

  const handleApplyStrokes = useCallback((targetFieldName: string, urls: string) => {
    setFieldValues((prev) => ({
      ...prev,
      [targetFieldName]: urls,
    }))
  }, [])

  // Merge full detail once background query resolves
  useEffect(() => {
    if (cardDetailQuery.data && open) {
      const detail = cardDetailQuery.data
      if (hydratedDetailRef.current === detail) return
      const hasDraft = JSON.stringify(fieldValues) !== JSON.stringify(initialFieldValues)
        || JSON.stringify(tags) !== JSON.stringify(initialTags) || deckId !== initialDeckId
      if (hydratedDetailRef.current && hasDraft) return
      hydratedDetailRef.current = detail
      initialWritePreconditionsRef.current = noteWritePreconditions(detail.note)
      const detailValues = detail.note.field_values || {}
      const detailTags = detail.note.tags || []
      const detailDeckId = detail.note.deck_id || null
      const pendingFields = Object.fromEntries(Object.entries(fieldValues).filter(([name, value]) =>
        JSON.stringify(value) !== JSON.stringify(initialFieldValues[name])))
      if (Object.entries(pendingFields).some(([name, value]) =>
        JSON.stringify(detailValues[name]) !== JSON.stringify(initialFieldValues[name])
        && JSON.stringify(detailValues[name]) !== JSON.stringify(value))) {
        initialDetailConflictRef.current = true
      }

      setFieldValues((current) => {
        // If form has not been modified by user yet, adopt authoritative detailValues directly
        const isPristine = Object.keys(current).every(
          (k) => JSON.stringify(current[k] ?? '') === JSON.stringify(initialFieldValues[k] ?? '')
        )
        if (isPristine) {
          return { ...detailValues }
        }
        return {
          ...detailValues,
          ...pendingFields,
        }
      })
      setInitialFieldValues(detailValues)
      setTags((current) => [...new Set([
        ...detailTags.filter((tag) => !initialTags.includes(tag) || current.includes(tag)),
        ...current.filter((tag) => !initialTags.includes(tag)),
      ])])
      setInitialTags(detailTags)
      setDeckId((current) => current !== initialDeckId ? current : detailDeckId)
      setInitialDeckId(detailDeckId)
    }
  }, [cardDetailQuery.data, open, initialFieldValues, fieldValues, tags, initialTags, deckId, initialDeckId])

  const handleAddTag = useCallback(() => {
    const trimmed = newTagInput.trim()
    if (!trimmed || tags.includes(trimmed)) return
    setTags((prev) => [...prev, trimmed])
    setNewTagInput('')
  }, [newTagInput, tags])

  const handleRemoveTag = useCallback((tagToRemove: string) => {
    setTags((prev) => prev.filter((t) => t !== tagToRemove))
  }, [])

  const handleRevert = useCallback(() => {
    initialDetailConflictRef.current = false
    setFieldValues(initialFieldValues)
    setTags(initialTags)
    setDeckId(initialDeckId)
    setNewTagInput('')
  }, [initialFieldValues, initialTags, initialDeckId])

  const isDirty = useMemo(() => {
    if (!open || !cardId) return false
    if (deckId !== initialDeckId) return true
    if (JSON.stringify(tags) !== JSON.stringify(initialTags)) return true
    const currentKeys = Object.keys(fieldValues)
    const initialKeys = Object.keys(initialFieldValues)
    if (currentKeys.length !== initialKeys.length) return true
    for (const key of currentKeys) {
      if (JSON.stringify(fieldValues[key] ?? '') !== JSON.stringify(initialFieldValues[key] ?? '')) return true
    }
    return false
  }, [cardId, deckId, fieldValues, initialDeckId, initialFieldValues, initialTags, open, tags])

  // Media resolver map: maps filename or relative reference to fully resolved proxy URL
  const mediaMap = useMemo(() => {
    const map = new Map<string, string>()
    if (cardDetailQuery.data?.media_assets) {
      for (const asset of cardDetailQuery.data.media_assets) {
        if (asset.filename && asset.url) {
          map.set(asset.filename.toLowerCase(), resolveBackendUrl(asset.url))
        }
      }
    }
    if (content?.media) {
      for (const m of content.media) {
        if (m.filename && m.proxy_url) {
          map.set(m.filename.toLowerCase(), resolveBackendUrl(m.proxy_url))
        }
      }
    }
    return map
  }, [cardDetailQuery.data?.media_assets, content?.media])

  const mediaResolver = useCallback(
    (rawRef: string) => {
      return mediaMap.get(rawRef.toLowerCase())
    },
    [mediaMap],
  )

  // Save Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: {
      field_values: Record<string, unknown>
      deck_id?: number
      tags?: string[]
    }) => {
      if (initialDetailConflictRef.current) {
        return Promise.reject(new Error('Nội dung đã thay đổi. Hoàn tác và tải lại trước khi lưu.'))
      }
      return appApi.mutate<UpdateCardResponse>(`/browse/cards/${cardId}`, 'PATCH', {
        ...payload, ...initialWritePreconditionsRef.current,
      })
    },
    onSuccess: async (data) => {
      toast.success(t('quick_edit.saved_success'))
      const committedFieldValues = data?.detail?.note?.field_values || fieldValues
      if (data?.detail?.note) initialWritePreconditionsRef.current = noteWritePreconditions(data.detail.note)
      setInitialFieldValues(committedFieldValues)
      setFieldValues(committedFieldValues)
      setInitialTags(tags)
      setInitialDeckId(deckId)

      if (cardId) {
        const mediaAssets: StudyMediaArtifact[] = (data?.detail?.media_assets || []).map((asset) => ({
          id: asset.id,
          field_name: asset.field_name || '',
          filename: asset.filename || '',
          mime_type: asset.mime_type || '',
          sha256: '',
          proxy_url: asset.url,
        }))
        const options = {
          media: mediaAssets.length > 0 ? mediaAssets : undefined,
          noteId: data?.detail?.note?.id != null ? String(data.detail.note.id) : undefined,
        }
        if (options.media || options.noteId) {
          await onCardUpdated(cardId, committedFieldValues, options)
        } else {
          await onCardUpdated(cardId, committedFieldValues)
        }
      }

      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', cardId] })

      onClose()
    },
    onError: (error: Error) => {
      toast.error(t('quick_edit.save_error'), { description: error.message })
    },
  })

  // Resolve fields definition
  const fieldDefs = useMemo(() => {
    if (!open) return []

    const rawDefs =
      cardDetailQuery.data?.fields && cardDetailQuery.data.fields.length > 0
        ? cardDetailQuery.data.fields
        : template?.binding_projection
        ? template.binding_projection.field_defs
        : template?.field_defs && template.field_defs.length > 0
        ? template.field_defs
        : Object.keys(fieldValues).map((name, index) => ({
            name,
            position: index,
            required: false,
            field_type: 'text',
          }))

    return rawDefs.map((f, index) => {
      const val = fieldValues[f.name] ?? initialFieldValues[f.name] ?? ''
      const detectedType = inferFieldType(f.field_type, f.name, val)
      return {
        name: f.name,
        position: f.position ?? index,
        required: Boolean(f.required),
        field_type: detectedType,
      }
    })
  }, [open, cardDetailQuery.data?.fields, template?.binding_projection, template?.field_defs, fieldValues, initialFieldValues])

  const isDetailReady = Boolean(cardId && cardDetailQuery.data?.card.card_id === cardId)

  const handleSubmit = useCallback(() => {
    if (!isDetailReady || hydratedDetailRef.current?.card.card_id !== cardId
      || !isDirty || updateMutation.isPending || !cardId || fieldDefs.some((field) => invalidArrayFields[field.name])) return
    const values = serializeArrayFieldValues(fieldValues, fieldDefs)
    updateMutation.mutate({
      field_values: values,
      deck_id: deckId || undefined,
      tags,
    })
  }, [isDetailReady, isDirty, updateMutation, cardId, fieldValues, fieldDefs, deckId, tags, invalidArrayFields])

  const deckList = cardDetailQuery.data?.decks || []

  // Available on the first open render, before the init effects above run, so
  // each field editor picks Input or Textarea from the stored value.
  const editorSeedValues = cardDetailQuery.data?.note.field_values ?? content?.field_values ?? initialFieldValues

  return {
    fieldValues,
    setFieldValues,
    tags,
    newTagInput,
    setNewTagInput,
    deckId,
    setDeckId,
    handleAddTag,
    handleRemoveTag,
    handleRevert,
    handleApplyStrokes,
    isDirty,
    isDetailReady,
    hasInvalidFields: fieldDefs.some((field) => invalidArrayFields[field.name]),
    handleFieldValidityChange,
    mediaResolver,
    handleSubmit,
    isSubmitting: updateMutation.isPending,
    fieldDefs,
    deckList,
    editorSeedValues,
  }
}

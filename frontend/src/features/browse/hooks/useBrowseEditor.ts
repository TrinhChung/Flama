import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { updateCardFieldValues } from '@/entities/flashcard/contentUpdates'
import { noteWritePreconditions } from '@/entities/flashcard/fields'
import { NOTE_TAG_MAX_COUNT, NOTE_TAG_MAX_LENGTH, tagDedupeKey } from '@/entities/flashcard'
import { browseApi } from '../api/browseApi'
import { parseDeckIdParam } from '../utils/browseParams'
import type { useBrowseFilters } from './useBrowseFilters'
import type { useBrowseData } from './useBrowseData'
import type { useBrowseSelection } from './useBrowseSelection'

type BrowseEditorOptions = {
  urlDeckId: string | null
  urlCardId: string | null
  filters: ReturnType<typeof useBrowseFilters>
  data: ReturnType<typeof useBrowseData>
  selection: ReturnType<typeof useBrowseSelection>
}

export function useBrowseEditor({ urlDeckId, urlCardId, filters, data, selection }: BrowseEditorOptions) {
  const { t } = useTranslation('browse')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { selectedDeckId, setSelectedDeckId } = filters
  const { decksQuery, noteTypesQuery } = data
  const { setSelectedCards } = selection
  // Right Pane: Active Card Selection & Editor State
  const [activeCardId, setActiveCardId] = useState<string | null>(
    urlCardId ? urlCardId : null,
  )
  const [isCreatingCard, setIsCreatingCard] = useState(false)
  const [createNoteTypeId, setCreateNoteTypeId] = useState<string | null>(null)

  // Mobile View Switcher Tab State: 'decks' | 'cards' | 'editor'
  const [mobileTab, setMobileTab] = useState<'decks' | 'cards' | 'editor'>(
    urlCardId ? 'editor' : 'cards',
  )

  // Sync state if URL search parameters change on initial mount
  const initialUrlDeckSyncedRef = useRef(false)
  useEffect(() => {
    if (!initialUrlDeckSyncedRef.current) {
      initialUrlDeckSyncedRef.current = true
      const parsedDeckId = parseDeckIdParam(urlDeckId)
      if (parsedDeckId !== null) {
        setSelectedDeckId(parsedDeckId)
      }
    }
    if (urlCardId) {
      setActiveCardId(urlCardId)
      setIsCreatingCard(false)
      setMobileTab('editor')
    }
  }, [urlDeckId, urlCardId, setSelectedDeckId])

  const [editFieldValues, setEditFieldValues] = useState<Record<string, unknown>>({})
  const [editDeckId, setEditDeckId] = useState<number | null>(null)
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')
  const [arrayViewMode, setArrayViewMode] = useState<'normal' | 'code'>('normal')

  // Initial Snapshot for Dirty Tracking
  const [initialFieldValues, setInitialFieldValues] = useState<Record<string, unknown>>({})
  const [initialDeckId, setInitialDeckId] = useState<number | null>(null)
  const [initialTags, setInitialTags] = useState<string[]>([])
  const hydratedCardIdRef = useRef<string | null>(null)
  const initialWritePreconditionsRef = useRef<ReturnType<typeof noteWritePreconditions>>({})
  const editorStateRef = useRef({
    cardId: activeCardId, fields: editFieldValues, deckId: editDeckId, tags: editTags,
    initialFields: initialFieldValues, initialDeckId, initialTags,
  })
  editorStateRef.current = {
    cardId: activeCardId, fields: editFieldValues, deckId: editDeckId, tags: editTags,
    initialFields: initialFieldValues, initialDeckId, initialTags,
  }

  useEffect(() => {
    if (isCreatingCard && !createNoteTypeId && noteTypesQuery.data?.items?.length) {
      setCreateNoteTypeId(noteTypesQuery.data.items[0].id)
    }
  }, [isCreatingCard, createNoteTypeId, noteTypesQuery.data?.items])

  // Selected Card Detail Query
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', activeCardId],
    queryFn: ({ signal }) => browseApi.fetchCardDetail(activeCardId!, signal),
    enabled: Boolean(activeCardId),
  })

  useEffect(() => {
    if (!activeCardId || isCreatingCard) {
      hydratedCardIdRef.current = null
      initialWritePreconditionsRef.current = {}
      return
    }
    if (cardDetailQuery.data && String(cardDetailQuery.data.card.card_id) === activeCardId) {
      const editor = editorStateRef.current
      const isPristine = JSON.stringify(editor.fields) === JSON.stringify(editor.initialFields)
        && editor.deckId === editor.initialDeckId
        && JSON.stringify(editor.tags) === JSON.stringify(editor.initialTags)
      if (hydratedCardIdRef.current === activeCardId && !isPristine) return
      hydratedCardIdRef.current = activeCardId
      const fieldValues = cardDetailQuery.data.note.field_values || {}
      initialWritePreconditionsRef.current = noteWritePreconditions(cardDetailQuery.data.note)
      const deckId = cardDetailQuery.data.note.deck_id || null
      const tags = cardDetailQuery.data.note.tags || []

      setEditFieldValues(fieldValues)
      setEditDeckId(deckId)
      setEditTags(tags)

      setInitialFieldValues(fieldValues)
      setInitialDeckId(deckId)
      setInitialTags(tags)
    }
  }, [cardDetailQuery.data, activeCardId, isCreatingCard])

  const isDirty = (() => {
    if (!activeCardId || !cardDetailQuery.data) return false
    if (editDeckId !== initialDeckId) return true
    if (JSON.stringify(editTags) !== JSON.stringify(initialTags)) return true
    const currentKeys = Object.keys(editFieldValues)
    const initialKeys = Object.keys(initialFieldValues)
    if (currentKeys.length !== initialKeys.length) return true
    for (const key of currentKeys) {
      if (JSON.stringify(editFieldValues[key] ?? '') !== JSON.stringify(initialFieldValues[key] ?? '')) return true
    }
    return false
  })()

  const handleRevert = () => {
    setEditFieldValues(initialFieldValues)
    setEditDeckId(initialDeckId)
    setEditTags(initialTags)
  }

  const handleStartCreateCard = () => {
    setIsCreatingCard(true)
    setActiveCardId(null)
    setSelectedCards([])

    const defaultDeckId = selectedDeckId ?? decksQuery.data?.decks?.[0]?.id ?? null
    setEditDeckId(defaultDeckId)

    const currentDeck = decksQuery.data?.decks?.find((d) => d.id === defaultDeckId)
    const availableNoteTypes = noteTypesQuery.data?.items || []
    const resolvedNoteTypeId =
      currentDeck?.note_type_id ||
      cardDetailQuery.data?.note?.note_type_id ||
      availableNoteTypes.find((nt) => nt.field_defs?.some((f) => f.name.toLowerCase() === 'word'))?.id ||
      availableNoteTypes.find((nt) => !nt.field_defs?.some((f) => f.name.toLowerCase() === 'stt'))?.id ||
      availableNoteTypes[0]?.id

    if (resolvedNoteTypeId) {
      setCreateNoteTypeId(resolvedNoteTypeId)
    }

    setEditFieldValues({})
    setEditTags([])
    setNewTagInput('')
    setMobileTab('editor')
  }

  const handleCancelCreate = () => {
    setIsCreatingCard(false)
    setEditFieldValues({})
    setEditTags([])
    setNewTagInput('')
  }

  // Create Card / Note Mutation
  const createMutation = useMutation({
    mutationFn: (payload: {
      note_type_id: string
      deck_id: number
      field_values: Record<string, unknown>
      tags?: string[]
    }) =>
      browseApi.createNote(payload),
    onSuccess: async (data, variables) => {
      toast.success(t('toasts.create_success'))
      setIsCreatingCard(false)

      const targetDeckId = variables.deck_id
      if (targetDeckId !== undefined && targetDeckId !== null) {
        setSelectedDeckId(targetDeckId)
      }

      const rawCardId = data?.first_card_id ?? data?.card_ids?.[0]
      const newCardId = rawCardId !== undefined && rawCardId !== null ? String(rawCardId) : null

      if (newCardId) {
        setActiveCardId(newCardId)
      }

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] }),
        queryClient.invalidateQueries({ queryKey: ['browse', 'decks'] }),
        queryClient.invalidateQueries({ queryKey: bootstrapQueryKey }),
        newCardId
          ? queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', newCardId] })
          : Promise.resolve(),
      ])

      if (newCardId) {
        setActiveCardId(newCardId)
      }
      setMobileTab('editor')
    },
    onError: (error: Error) => {
      toast.error(t('toasts.create_error'), { description: error.message })
    },
  })

  // Update Mutation
  const updateMutation = useMutation({
    mutationFn: async (payload: { field_values: Record<string, unknown>; deck_id?: number; tags?: string[] }) => {
      const cardId = activeCardId
      const noteId = cardDetailQuery.data?.note.id
      const draft = { fields: editFieldValues, deckId: editDeckId, tags: editTags }
      const data = await browseApi.updateCard(cardId!, {
        ...payload, ...initialWritePreconditionsRef.current,
      })
      return { data, cardId, noteId, draft }
    },
    onSuccess: async ({ data, cardId, noteId, draft }) => {
      if (urlDeckId) {
        toast.success(t('toasts.save_success'), {
          duration: 2000,
          action: {
            label: t('toasts.back_to_study'),
            onClick: () => navigate(`/study?deck_id=${urlDeckId}`),
          },
        })
      } else {
        toast.success(t('toasts.save_success'), { duration: 1200 })
      }
      const committed = data.detail.note
      if (cardId === editorStateRef.current.cardId) {
        initialWritePreconditionsRef.current = noteWritePreconditions(committed)
        setInitialFieldValues(committed.field_values)
        setInitialDeckId(committed.deck_id ?? null)
        setInitialTags(committed.tags)
        setEditDeckId((current) => current === draft.deckId ? committed.deck_id ?? null : current)
        setEditTags((current) => JSON.stringify(current) === JSON.stringify(draft.tags) ? committed.tags : current)
        setEditFieldValues((current) => {
          const next = { ...committed.field_values }
          for (const [name, value] of Object.entries(current)) {
            if (JSON.stringify(value) !== JSON.stringify(draft.fields[name])) next[name] = value
          }
          return next
        })
      }
      if (cardId) {
        await updateCardFieldValues({ cardId, fieldValues: committed.field_values, noteId: committed.id || noteId })
      }
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', cardId] })
    },
    onError: (error: Error) => {
      toast.error(t('toasts.save_error'), { description: error.message })
    },
  })

  const handleActivateCard = useCallback((cardId: string) => {
    setIsCreatingCard(false)
    setActiveCardId(cardId)
    setMobileTab('editor')
  }, [])

  // Logical-overlay clones: the backend rejects deck moves, tag edits and media uploads.
  const activeDetail = cardDetailQuery.data
  const isCloneCard = Boolean(activeDetail?.note.deck_install_id)
  const canUploadMedia = !isCloneCard && activeDetail?.can_upload_media !== false

  const handleAddTag = () => {
    const tag = newTagInput.trim().slice(0, NOTE_TAG_MAX_LENGTH)
    if (!tag) return
    const key = tagDedupeKey(tag)
    if (editTags.some((existing) => tagDedupeKey(existing) === key)) return
    if (editTags.length >= NOTE_TAG_MAX_COUNT) {
      toast.error(t('editor.tag_limit', { count: NOTE_TAG_MAX_COUNT }))
      return
    }
    setEditTags([...editTags, tag])
    setNewTagInput('')
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setEditTags(editTags.filter((t) => t !== tagToRemove))
  }


  return { activeCardId, setActiveCardId, isCreatingCard, setIsCreatingCard, createNoteTypeId, setCreateNoteTypeId, mobileTab, setMobileTab, editFieldValues, setEditFieldValues, editDeckId, setEditDeckId, editTags, setEditTags, newTagInput, setNewTagInput, arrayViewMode, setArrayViewMode, initialFieldValues, initialDeckId, initialTags, isDirty, isCloneCard, canUploadMedia, cardDetailQuery, handleRevert, handleStartCreateCard, handleCancelCreate, createMutation, updateMutation, handleAddTag, handleRemoveTag, handleActivateCard }
}

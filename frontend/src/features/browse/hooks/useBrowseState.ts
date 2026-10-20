import '@/shared/config/i18n'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { bootstrapQueryKey, useBootstrap } from '@/shared/api/bootstrap'
import { ApiError, apiBlob } from '@/shared/api/client'
import { updateCardFieldValues } from '@/entities/flashcard/model/cardContentUpdates'
import { NOTE_TAG_MAX_COUNT, NOTE_TAG_MAX_LENGTH, tagDedupeKey } from '@/entities/flashcard'
import {
  type BrowseTtsSettings,
  loadStoredBrowseTtsSettings,
  resetStoredBrowseTtsSettings,
  saveStoredBrowseTtsSettings,
} from '../services/ttsSettingsStorage'
import { cleanTextForTts } from '@/features/audio/services/ttsTextNormalizer'
import { fieldValueEditorText } from '@/lib/arrayField'
import { noteWritePreconditions } from '@/lib/noteWritePreconditions'
import {
  type BrowseCardRow,
  type BrowseCardsResponse,
  type BrowseDeck,
  type BrowseSortBy,
  type BrowseSortDir,
  type BrowseStatusFilter,
  type CardDetailResponse,
  type NoteTypeSummary,
} from '../types'
import { parseDeckIdParam } from '../utils/browseParams'

const EMPTY_BROWSE_CARDS: BrowseCardRow[] = []

/** A 4xx (bad filter, missing deck) will fail the same way again. */
function retryUnlessClientError(failureCount: number, error: Error) {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false
  return failureCount < 1
}

export function useBrowseState() {
  const { t } = useTranslation('browse')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlDeckId = searchParams.get('deck_id')
  const urlCardId = searchParams.get('card_id')

  const queryClient = useQueryClient()
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  // Left Pane: Deck Selection & Search
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(() => parseDeckIdParam(urlDeckId))
  const [deckSearch, setDeckSearch] = useState('')

  // Center Pane: Filter, Search, Sort & Paging
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [statusFilter, setStatusFilterState] = useState<BrowseStatusFilter>('all')
  const [sortBy, setSortBy] = useState<BrowseSortBy>('due')
  const [sortDir, setSortDir] = useState<BrowseSortDir>('asc')
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState<number>(() => {
    const saved = localStorage.getItem('flama_browse_per_page')
    if (saved) {
      const parsed = parseInt(saved, 10)
      if (!isNaN(parsed) && [20, 50, 100, 200, 500].includes(parsed)) {
        return parsed
      }
    }
    return 100
  })
  const [selectedCards, setSelectedCards] = useState<string[]>([])
  const selectedCardSet = useMemo(() => new Set(selectedCards), [selectedCards])

  const handlePerPageChange = useCallback((newPerPage: number) => {
    setPerPage(newPerPage)
    setPage(1)
    localStorage.setItem('flama_browse_per_page', String(newPerPage))
  }, [])

  const setStatusFilter = useCallback((next: BrowseStatusFilter) => {
    setStatusFilterState(next)
    setPage(1)
  }, [])

  const handleSortChange = useCallback((field: BrowseSortBy) => {
    if (field === sortBy) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
    setPage(1)
  }, [sortBy])

  // VoiceVox TTS Audio Generation Modal State (read from storage once)
  const [initialTtsSettings] = useState(loadStoredBrowseTtsSettings)
  const [isTtsModalOpen, setIsTtsModalOpen] = useState(false)
  const [isLocalAudioModalOpen, setIsLocalAudioModalOpen] = useState(false)
  const [isStrokeModalOpen, setIsStrokeModalOpen] = useState(false)
  const [strokeModalMode, setStrokeModalMode] = useState<'single' | 'batch'>('batch')
  const [strokeModalCardId, setStrokeModalCardId] = useState<string | null>(null)
  const [localAudioEngineId, setLocalAudioEngineId] = useState<'voicevox' | 'kokoro'>('voicevox')
  const [localAudioDefaultVoiceId, setLocalAudioDefaultVoiceId] = useState<string | undefined>(undefined)
  const [localAudioTargetCardIds, setLocalAudioTargetCardIds] = useState<string[]>([])
  const effectiveNoteTypeNameRef = useRef<string | undefined>(undefined)

  const [ttsSourceField, setTtsSourceFieldState] = useState<string>(
    initialTtsSettings.sourceField || 'Word'
  )
  const setTtsSourceField = (val: string | ((prev: string) => string)) => {
    setTtsSourceFieldState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      const noteTypeName = effectiveNoteTypeNameRef.current
      const updates: Partial<BrowseTtsSettings> = { sourceField: next }
      if (noteTypeName) {
        const currentMapping = loadStoredBrowseTtsSettings().fieldMappingByNoteType || {}
        updates.fieldMappingByNoteType = {
          ...currentMapping,
          [noteTypeName]: {
            ...(currentMapping[noteTypeName] || {}),
            sourceField: next,
          },
        }
      }
      saveStoredBrowseTtsSettings(updates)
      return next
    })
  }

  const [ttsDestinationField, setTtsDestinationFieldState] = useState<string>(
    initialTtsSettings.destinationField || 'Audio'
  )
  const setTtsDestinationField = (val: string | ((prev: string) => string)) => {
    setTtsDestinationFieldState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      const noteTypeName = effectiveNoteTypeNameRef.current
      const updates: Partial<BrowseTtsSettings> = { destinationField: next }
      if (noteTypeName) {
        const currentMapping = loadStoredBrowseTtsSettings().fieldMappingByNoteType || {}
        updates.fieldMappingByNoteType = {
          ...currentMapping,
          [noteTypeName]: {
            ...(currentMapping[noteTypeName] || {}),
            destinationField: next,
          },
        }
      }
      saveStoredBrowseTtsSettings(updates)
      return next
    })
  }
  
  const [ttsCharacter, setTtsCharacterState] = useState<string>(initialTtsSettings.character)
  const setTtsCharacter = (val: string | ((prev: string) => string)) => {
    setTtsCharacterState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ character: next })
      return next
    })
  }

  const [ttsApiKey, setTtsApiKey] = useState(() => {
    return localStorage.getItem('flama_voicevox_api_key') || ''
  })
  const [isKeySaved, setIsKeySaved] = useState(false)
  const [isSavingKey, setIsSavingKey] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)

  const [ttsAppendAudio, setTtsAppendAudioState] = useState<boolean>(initialTtsSettings.appendAudio)
  const setTtsAppendAudio = (val: boolean | ((prev: boolean) => boolean)) => {
    setTtsAppendAudioState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ appendAudio: next })
      return next
    })
  }

  const [ttsUseOpus, setTtsUseOpusState] = useState<boolean>(initialTtsSettings.useOpus)
  const setTtsUseOpus = (val: boolean | ((prev: boolean) => boolean)) => {
    setTtsUseOpusState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ useOpus: next })
      return next
    })
  }

  const [ttsVolumeScale, setTtsVolumeScaleState] = useState<number>(initialTtsSettings.volumeScale)
  const setTtsVolumeScale = (val: number | ((prev: number) => number)) => {
    setTtsVolumeScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ volumeScale: next })
      return next
    })
  }

  const [ttsPitch, setTtsPitchState] = useState<number>(initialTtsSettings.pitch)
  const setTtsPitch = (val: number | ((prev: number) => number)) => {
    setTtsPitchState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ pitch: next })
      return next
    })
  }

  const [ttsSpeed, setTtsSpeedState] = useState<number>(initialTtsSettings.speed)
  const setTtsSpeed = (val: number | ((prev: number) => number)) => {
    setTtsSpeedState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ speed: next })
      return next
    })
  }

  const [ttsIntonationScale, setTtsIntonationScaleState] = useState<number>(initialTtsSettings.intonationScale)
  const setTtsIntonationScale = (val: number | ((prev: number) => number)) => {
    setTtsIntonationScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ intonationScale: next })
      return next
    })
  }

  const [ttsInitialSilence, setTtsInitialSilenceState] = useState<number>(initialTtsSettings.initialSilence)
  const setTtsInitialSilence = (val: number | ((prev: number) => number)) => {
    setTtsInitialSilenceState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ initialSilence: next })
      return next
    })
  }

  const [ttsFinalSilence, setTtsFinalSilenceState] = useState<number>(initialTtsSettings.finalSilence)
  const setTtsFinalSilence = (val: number | ((prev: number) => number)) => {
    setTtsFinalSilenceState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      saveStoredBrowseTtsSettings({ finalSilence: next })
      return next
    })
  }

  const [isPreviewing, setIsPreviewing] = useState(false)

  // Worksheet Generator Modal State
  const [isWorksheetModalOpen, setIsWorksheetModalOpen] = useState(false)
  const [worksheetTargetDeckId, setWorksheetTargetDeckId] = useState<number | null>(null)
  const [worksheetTargetCardIds, setWorksheetTargetCardIds] = useState<string[] | undefined>(undefined)

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
  }, [urlDeckId, urlCardId])

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

  // Debounce main search query; only a changed query sends paging back to 1.
  useEffect(() => {
    const nextQuery = queryText.trim()
    if (nextQuery === debouncedQuery) return
    const timer = window.setTimeout(() => {
      setDebouncedQuery(nextQuery)
      setPage(1)
    }, 400)
    return () => window.clearTimeout(timer)
  }, [queryText, debouncedQuery])

  // Decks Tree Query
  const decksQuery = useQuery({
    queryKey: ['browse', 'decks'],
    queryFn: () => appApi.get<{ decks: BrowseDeck[] }>('/browse/decks'),
  })

  // Note Types Query for Card Creation
  const noteTypesQuery = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<{ items: NoteTypeSummary[] }>('/note-types'),
  })

  useEffect(() => {
    if (isCreatingCard && !createNoteTypeId && noteTypesQuery.data?.items?.length) {
      setCreateNoteTypeId(noteTypesQuery.data.items[0].id)
    }
  }, [isCreatingCard, createNoteTypeId, noteTypesQuery.data?.items])

  // Cards List Query
  const cardsQuery = useQuery({
    queryKey: [
      'browse',
      'cards',
      debouncedQuery,
      selectedDeckId,
      statusFilter,
      sortBy,
      sortDir,
      page,
      perPage,
    ],
    queryFn: () =>
      appApi.get<BrowseCardsResponse>('/browse/cards', {
        q: debouncedQuery,
        deck_id: selectedDeckId !== null ? selectedDeckId : '',
        status: statusFilter,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        per_page: perPage,
      }),
    placeholderData: keepPreviousData,
    retry: retryUnlessClientError,
  })

  const cards = cardsQuery.data?.items || EMPTY_BROWSE_CARDS

  // Pull the page back inside the result, e.g. after deleting the last rows.
  const confirmedPageCount = cardsQuery.isPlaceholderData ? null : cardsQuery.data?.pages
  useEffect(() => {
    if (confirmedPageCount === undefined || confirmedPageCount === null) return
    const lastPage = Math.max(1, confirmedPageCount)
    if (page > lastPage) setPage(lastPage)
  }, [confirmedPageCount, page])

  // Retain identity only for selected rows, including selections on other pages.
  const selectedNoteIdsRef = useRef(new Map<string, string>())
  useEffect(() => {
    for (const id of selectedNoteIdsRef.current.keys()) {
      if (!selectedCardSet.has(id)) selectedNoteIdsRef.current.delete(id)
    }
    for (const row of cards) {
      if (selectedCardSet.has(row.card_id)) selectedNoteIdsRef.current.set(row.card_id, row.note_id)
    }
  }, [cards, selectedCardSet])

  // Keyboard shortcuts
  const cardsRef = useRef(cards)
  cardsRef.current = cards
  const selectedCardsCountRef = useRef(selectedCards.length)
  selectedCardsCountRef.current = selectedCards.length

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement
      const isEditingText =
        activeEl instanceof HTMLInputElement ||
        activeEl instanceof HTMLTextAreaElement ||
        Boolean((activeEl as HTMLElement | null)?.isContentEditable)

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        if (!isEditingText && cardsRef.current.length > 0) {
          e.preventDefault()
          setSelectedCards(cardsRef.current.map((c) => c.card_id))
        }
      } else if (e.key === 'Escape') {
        if (!isEditingText && selectedCardsCountRef.current > 0) {
          e.preventDefault()
          setSelectedCards([])
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Selected Card Detail Query
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', activeCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${activeCardId}`),
    enabled: Boolean(activeCardId),
  })

  // Sample card detail query when no card is actively selected but modal is open
  const sampleCardId = activeCardId || (cards.length > 0 ? String(cards[0].card_id) : null)
  const deckSampleQuery = useQuery({
    queryKey: ['browse', 'card-detail-sample', sampleCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${sampleCardId}`),
    enabled: Boolean(!activeCardId && sampleCardId && (isTtsModalOpen || isLocalAudioModalOpen)),
    staleTime: 5 * 60 * 1000,
  })

  const effectiveCardDetail = cardDetailQuery.data || deckSampleQuery.data

  // Populate editor state
  const ttsSourceFieldRef = useRef(ttsSourceField)
  ttsSourceFieldRef.current = ttsSourceField
  const ttsDestinationFieldRef = useRef(ttsDestinationField)
  ttsDestinationFieldRef.current = ttsDestinationField

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

  useEffect(() => {
    effectiveNoteTypeNameRef.current = effectiveCardDetail?.note?.note_type_name || undefined
    if (effectiveCardDetail?.fields && effectiveCardDetail.fields.length > 0) {
      const fields = effectiveCardDetail.fields
      const sourceFieldNames = fields
        .filter((field) => !['image', 'audio', 'diagram'].includes(String(field.field_type || '').toLowerCase()))
        .map((field) => field.name)
      const audioFieldNames = fields
        .filter((field) => String(field.field_type || '').toLowerCase() === 'audio')
        .map((field) => field.name)

      const noteTypeName = effectiveCardDetail.note?.note_type_name || undefined
      const storedSettings = loadStoredBrowseTtsSettings()
      const noteTypeMapping = noteTypeName ? storedSettings.fieldMappingByNoteType?.[noteTypeName] : undefined

      const currentSource = ttsSourceFieldRef.current
      if (currentSource && sourceFieldNames.includes(currentSource)) {
        // Keep current selected source field
      } else if (noteTypeMapping?.sourceField && sourceFieldNames.includes(noteTypeMapping.sourceField)) {
        setTtsSourceField(noteTypeMapping.sourceField)
      } else if (storedSettings.sourceField && sourceFieldNames.includes(storedSettings.sourceField)) {
        setTtsSourceField(storedSettings.sourceField)
      } else {
        const sourcePriority = [
          'Reading', 'reading',
          'Word', 'word',
          'Expression', 'expression',
          'Kanji', 'kanji',
          'Hanzi', 'hanzi',
          'Simplified', 'simplified',
          'Traditional', 'traditional',
          'Front', 'front',
          'Vocab', 'vocab',
          'Vocabulary', 'vocabulary',
          'Term', 'term',
          'Text', 'text',
        ]
        let foundSource = ''
        for (const p of sourcePriority) {
          const match = sourceFieldNames.find((f) => f.toLowerCase() === p.toLowerCase())
          if (match) {
            foundSource = match
            break
          }
        }
        setTtsSourceField(foundSource || (sourceFieldNames.length > 0 ? sourceFieldNames[0] : ''))
      }

      const currentDest = ttsDestinationFieldRef.current
      if (currentDest && audioFieldNames.includes(currentDest)) {
        // Keep current selected destination field
      } else if (noteTypeMapping?.destinationField && audioFieldNames.includes(noteTypeMapping.destinationField)) {
        setTtsDestinationField(noteTypeMapping.destinationField)
      } else if (storedSettings.destinationField && audioFieldNames.includes(storedSettings.destinationField)) {
        setTtsDestinationField(storedSettings.destinationField)
      } else {
        const destPriority = [
          'Audio', 'audio',
          'AudioReading', 'audioreading',
          'Sound', 'sound',
          'AudioWord', 'audioword',
          'Pronunciation', 'pronunciation',
          'Voice', 'voice',
        ]
        let foundDest = ''
        for (const p of destPriority) {
          const match = audioFieldNames.find((f) => f.toLowerCase() === p.toLowerCase())
          if (match) {
            foundDest = match
            break
          }
        }
        setTtsDestinationField(foundDest || (audioFieldNames.length > 0 ? audioFieldNames[0] : ''))
      }
    }
  }, [effectiveCardDetail])

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
      appApi.mutate<{ id: string; card_ids?: Array<string | number>; first_card_id?: string | number }>(
        '/notes',
        'POST',
        payload,
      ),
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
      const data = await appApi.mutate<{ detail: CardDetailResponse }>(`/browse/cards/${cardId}`, 'PATCH', {
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

  // Single Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: async (cardId: string) => {
      const detail = cardDetailQuery.data
      const noteId = cards.find((row) => row.card_id === cardId)?.note_id
        ?? (detail?.card.card_id === cardId ? detail.note.id : undefined)
      if (!noteId) throw new Error(t('toasts.delete_error'))
      await appApi.mutate(`/browse/notes/${noteId}`, 'DELETE')
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
      const res = await appApi.mutate<{ success: boolean; deleted_count?: number }>(
        '/browse/notes/batch-delete',
        'POST',
        { note_ids: noteIds },
      )
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

  const targetTtsCardIds = selectedCards.length > 0 ? selectedCards : activeCardId ? [activeCardId] : []

  // VoiceVox TTS Generate Mutation
  const generateTtsMutation = useMutation({
    mutationFn: (payload: {
      card_ids?: string[]
      deck_id?: number
      source_field: string
      destination_field: string
      character_id?: string
      api_key?: string
      append_audio?: boolean
      use_opus?: boolean
      settings?: Record<string, number>
    }) => appApi.mutate('/browse/voicevox/generate', 'POST', payload),
    onMutate: () => {
      toast?.loading?.(t('toasts.generating_tts'), {
        id: 'generate-tts',
        description: t('toasts.generating_tts_desc'),
      })
    },
    onSuccess: () => {
      if (ttsApiKey.trim()) {
        void saveApiKeyIfValid(ttsApiKey, false)
      }
      toast.success(t('toasts.tts_success'), { id: 'generate-tts' })
      setIsTtsModalOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      if (activeCardId) {
        void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', activeCardId] })
      }
    },
    onError: (error: Error) => {
      toast.error(t('toasts.tts_error'), { id: 'generate-tts', description: error.message })
    },
  })

  // Fetch saved profile
  const ttsProfileQuery = useQuery({
    queryKey: ['voicevox-profile'],
    queryFn: () =>
      appApi.get<{
        profile?: {
          has_api_key: boolean
          key_status: string
        }
      }>('/api/tts/providers/voicevox/profile'),
    enabled: isTtsModalOpen,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (ttsProfileQuery.data?.profile?.has_api_key) {
      setIsKeySaved(true)
    }
  }, [ttsProfileQuery.data])

  const saveApiKeyIfValid = async (keyToSave: string, showToast = true) => {
    const trimmed = keyToSave.trim()
    if (!trimmed) return
    setIsSavingKey(true)
    localStorage.setItem('flama_voicevox_api_key', trimmed)
    try {
      await appApi.mutate('/api/tts/providers/voicevox/profile', 'PUT', {
        api_key: trimmed,
        validate_key: true,
      })
      setIsKeySaved(true)
      void queryClient.invalidateQueries({ queryKey: ['voicevox-profile'] })
      void queryClient.invalidateQueries({ queryKey: ['voicevox-voices'] })
      if (showToast) {
        toast.success(t('toasts.api_key_saved'))
      }
    } catch {
      // ignore
    } finally {
      setIsSavingKey(false)
    }
  }

  // Dynamic fetch voices. The key stays out of the queryKey so typing it does
  // not POST per keystroke; saving a key invalidates the list instead.
  const ttsApiKeyRef = useRef(ttsApiKey)
  ttsApiKeyRef.current = ttsApiKey
  const ttsVoicesQuery = useQuery({
    queryKey: ['voicevox-voices'],
    queryFn: () =>
      appApi.mutate<{ items: Array<{ id: string; label: string; speaker_name: string; style_name: string }> }>(
        '/api/tts/providers/voicevox/voices',
        'POST',
        { api_key: ttsApiKeyRef.current || undefined },
      ),
    enabled: isTtsModalOpen,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  // Preview VoiceVox
  const handlePreviewVoiceVox = async () => {
    const rawPreview =
      fieldValueEditorText(effectiveCardDetail?.note?.field_values?.[ttsSourceField]) ||
      cards[0]?.word ||
      cards[0]?.reading ||
      'こんにちは'
    const previewText = cleanTextForTts(rawPreview, 'voicevox') || 'こんにちは'
    setIsPreviewing(true)
    try {
      const blob = await apiBlob('/api/browse/voicevox/preview', {
        method: 'POST',
        body: JSON.stringify({
          text: previewText,
          character_id: ttsCharacter || undefined,
          api_key: ttsApiKey || undefined,
          use_opus: ttsUseOpus,
          settings: {
            volume_scale: ttsVolumeScale,
            pitch: ttsPitch,
            speed_scale: ttsSpeed,
            intonation_scale: ttsIntonationScale,
            initial_silence: ttsInitialSilence,
            final_silence: ttsFinalSilence,
          },
        }),
      })
      const url = URL.createObjectURL(blob)

      if (audioPlayerRef.current) {
        audioPlayerRef.current.src = url
        await audioPlayerRef.current.play()
      }
      if (ttsApiKey.trim()) {
        void saveApiKeyIfValid(ttsApiKey, false)
      }
      toast.success(t('toasts.playing_preview'))
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t('toasts.preview_error')
      toast.error(t('toasts.preview_error'), { description: message })
    } finally {
      setIsPreviewing(false)
    }
  }

  // Reset VoiceVox Settings
  const handleResetTtsDefaults = () => {
    resetStoredBrowseTtsSettings()
    setTtsSourceField('Word')
    setTtsDestinationField('Audio')
    setTtsCharacterState('')
    setTtsApiKey('')
    setTtsAppendAudioState(false)
    setTtsUseOpusState(false)
    setTtsVolumeScaleState(1.0)
    setTtsPitchState(0.0)
    setTtsSpeedState(1.0)
    setTtsIntonationScaleState(1.0)
    setTtsInitialSilenceState(0.1)
    setTtsFinalSilenceState(0.1)
    toast.info(t('toasts.reset_defaults'))
  }

  const allSelected = useMemo(
    () => cards.length > 0 && cards.every((card) => selectedCardSet.has(card.card_id)),
    [cards, selectedCardSet],
  )

  const handleToggleSelectAllCards = useCallback(() => {
    setSelectedCards(allSelected ? [] : cards.map((c) => c.card_id))
  }, [allSelected, cards])

  const handleToggleCardSelected = useCallback((cardId: string, selected: boolean) => {
    setSelectedCards((current) => {
      if (selected) return current.includes(cardId) ? current : [...current, cardId]
      return current.filter((id) => id !== cardId)
    })
  }, [])

  const handleActivateCard = useCallback((cardId: string) => {
    setIsCreatingCard(false)
    setActiveCardId(cardId)
    setMobileTab('editor')
  }, [])

  const { refetch: refetchCardsQuery } = cardsQuery
  const refetchCards = useCallback(() => {
    void refetchCardsQuery()
  }, [refetchCardsQuery])

  const selectedDeck =
    selectedDeckId !== null
      ? (decksQuery.data?.decks || []).find((deck) => deck.id === selectedDeckId) || null
      : null

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

  const handleResetDeckFilter = () => {
    setSelectedDeckId(null)
    setDeckSearch('')
    setPage(1)
  }

  const availableSourceFieldNames = Array.from(
    new Set(
      (effectiveCardDetail?.fields || [])
        .filter((field) => !['image', 'audio', 'diagram'].includes(String(field.field_type || '').toLowerCase()))
        .map((field) => field.name)
        .filter(Boolean),
    ),
  )
  const availableAudioFieldNames = Array.from(
    new Set(
      (effectiveCardDetail?.fields || [])
        .filter((field) => String(field.field_type || '').toLowerCase() === 'audio')
        .map((field) => field.name)
        .filter(Boolean),
    ),
  )

  return {
    navigate,
    urlDeckId,
    urlCardId,
    queryClient,
    audioPlayerRef,
    isAdmin,
    selectedDeckId,
    selectedDeck,
    setSelectedDeckId,
    deckSearch,
    setDeckSearch,
    queryText,
    setQueryText,
    debouncedQuery,
    statusFilter,
    setStatusFilter,
    sortBy,
    sortDir,
    page,
    setPage,
    perPage,
    handlePerPageChange,
    handleSortChange,
    selectedCards,
    selectedCardSet,
    setSelectedCards,
    handleToggleCardSelected,
    handleActivateCard,
    refetchCards,
    isTtsModalOpen,
    setIsTtsModalOpen,
    isLocalAudioModalOpen,
    setIsLocalAudioModalOpen,
    isStrokeModalOpen,
    setIsStrokeModalOpen,
    strokeModalMode,
    setStrokeModalMode,
    strokeModalCardId,
    setStrokeModalCardId,
    isWorksheetModalOpen,
    setIsWorksheetModalOpen,
    worksheetTargetDeckId,
    setWorksheetTargetDeckId,
    worksheetTargetCardIds,
    setWorksheetTargetCardIds,
    localAudioEngineId,
    setLocalAudioEngineId,
    localAudioDefaultVoiceId,
    setLocalAudioDefaultVoiceId,
    localAudioTargetCardIds,
    setLocalAudioTargetCardIds,
    ttsSourceField,
    setTtsSourceField,
    ttsDestinationField,
    setTtsDestinationField,
    ttsCharacter,
    setTtsCharacter,
    ttsApiKey,
    setTtsApiKey,
    isKeySaved,
    setIsKeySaved,
    isSavingKey,
    setIsSavingKey,
    showApiKey,
    setShowApiKey,
    ttsAppendAudio,
    setTtsAppendAudio,
    ttsUseOpus,
    setTtsUseOpus,
    ttsVolumeScale,
    setTtsVolumeScale,
    ttsPitch,
    setTtsPitch,
    ttsSpeed,
    setTtsSpeed,
    ttsIntonationScale,
    setTtsIntonationScale,
    ttsInitialSilence,
    setTtsInitialSilence,
    ttsFinalSilence,
    setTtsFinalSilence,
    isPreviewing,
    activeCardId,
    setActiveCardId,
    isCreatingCard,
    setIsCreatingCard,
    createNoteTypeId,
    setCreateNoteTypeId,
    noteTypesQuery,
    mobileTab,
    setMobileTab,
    editFieldValues,
    setEditFieldValues,
    editDeckId,
    setEditDeckId,
    editTags,
    setEditTags,
    newTagInput,
    setNewTagInput,
    initialFieldValues,
    initialDeckId,
    initialTags,
    isDirty,
    isCloneCard,
    canUploadMedia,
    allSelected,
    availableSourceFieldNames,
    availableAudioFieldNames,
    targetTtsCardIds,
    decksQuery,
    cardsQuery,
    cardDetailQuery,
    ttsProfileQuery,
    ttsVoicesQuery,
    handleRevert,
    handleStartCreateCard,
    handleCancelCreate,
    createMutation,
    updateMutation,
    deleteMutation,
    bulkDeleteMutation,
    generateTtsMutation,
    handleResetDeckFilter,
    handleToggleSelectAllCards,
    handleAddTag,
    handleRemoveTag,
    handlePreviewVoiceVox,
    handleResetTtsDefaults,
    saveApiKeyIfValid,
    cards,
    arrayViewMode,
    setArrayViewMode,
  }
}

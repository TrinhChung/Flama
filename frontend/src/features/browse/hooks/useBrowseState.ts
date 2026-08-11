import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { apiBlob } from '@/shared/api/client'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'

export type BrowseCardRow = {
  card_id: string
  note_id: string
  deck_id: number | null
  deck_name: string
  word: string
  reading: string
  meaning: string
  tags: string[]
  status: string
  due_label: string
}

export type BrowseCardsResponse = {
  items: BrowseCardRow[]
  page: number
  total: number
  pages: number
  has_next: boolean
}

export type BrowseDeck = {
  id: number
  name: string
  parent_id?: number | null
  path?: string
  counts?: {
    new?: number
    learn?: number
    due?: number
  }
}

export type CardDetailField = {
  name: string
  position: number
  required?: boolean
}

export type CardDetailResponse = {
  card: BrowseCardRow
  note: {
    id: string
    note_type_id?: string | null
    note_type_name?: string | null
    deck_id: number
    deck_name: string
    field_values: Record<string, string>
    tags: string[]
  }
  fields: CardDetailField[]
  decks?: Array<{ id: number; name: string; path?: string }>
}

export function useBrowseState() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const urlDeckId = searchParams.get('deck_id')
  const urlCardId = searchParams.get('card_id')

  const queryClient = useQueryClient()
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  const bootstrapQuery = useQuery({
    queryKey: ['bootstrap'],
    queryFn: () => appApi.getBootstrap(),
  })
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)

  // Left Pane: Deck Selection & Search
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(
    urlDeckId ? Number(urlDeckId) : null,
  )
  const [deckSearch, setDeckSearch] = useState('')

  // Center Pane: Filter, Search, Sort & Paging
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortBy, setSortBy] = useState('due')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
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

  const handlePerPageChange = (newPerPage: number) => {
    setPerPage(newPerPage)
    setPage(1)
    localStorage.setItem('flama_browse_per_page', String(newPerPage))
  }

  // VoiceVox TTS Audio Generation Modal State
  const [isTtsModalOpen, setIsTtsModalOpen] = useState(false)
  const [isLocalAudioModalOpen, setIsLocalAudioModalOpen] = useState(false)
  const [localAudioEngineId, setLocalAudioEngineId] = useState<'voicevox' | 'kokoro'>('voicevox')
  const [localAudioDefaultVoiceId, setLocalAudioDefaultVoiceId] = useState<string | undefined>(undefined)
  const [localAudioTargetCardIds, setLocalAudioTargetCardIds] = useState<string[]>([])
  const [ttsSourceField, setTtsSourceField] = useState('Word')
  const [ttsDestinationField, setTtsDestinationField] = useState('Audio')
  const [ttsCharacter, setTtsCharacter] = useState('')
  const [ttsApiKey, setTtsApiKey] = useState(() => {
    return localStorage.getItem('flama_voicevox_api_key') || ''
  })
  const [isKeySaved, setIsKeySaved] = useState(false)
  const [isSavingKey, setIsSavingKey] = useState(false)
  const [showApiKey, setShowApiKey] = useState(false)
  const [ttsAppendAudio, setTtsAppendAudio] = useState(false)
  const [ttsUseOpus, setTtsUseOpus] = useState(false)
  const [ttsVolumeScale, setTtsVolumeScale] = useState(1.0)
  const [ttsPitch, setTtsPitch] = useState(0.0)
  const [ttsSpeed, setTtsSpeed] = useState(1.0)
  const [ttsIntonationScale, setTtsIntonationScale] = useState(1.0)
  const [ttsInitialSilence, setTtsInitialSilence] = useState(0.1)
  const [ttsFinalSilence, setTtsFinalSilence] = useState(0.1)
  const [isPreviewing, setIsPreviewing] = useState(false)

  // Right Pane: Active Card Selection & Editor State
  const [activeCardId, setActiveCardId] = useState<string | null>(
    urlCardId ? urlCardId : null,
  )

  // Mobile View Switcher Tab State: 'decks' | 'cards' | 'editor'
  const [mobileTab, setMobileTab] = useState<'decks' | 'cards' | 'editor'>(
    urlCardId ? 'editor' : 'cards',
  )

  // Sync state if URL search parameters change
  useEffect(() => {
    if (urlDeckId) {
      setSelectedDeckId(Number(urlDeckId))
    }
    if (urlCardId) {
      setActiveCardId(urlCardId)
      setMobileTab('editor')
    }
  }, [urlDeckId, urlCardId])

  const [editFieldValues, setEditFieldValues] = useState<Record<string, string>>({})
  const [editDeckId, setEditDeckId] = useState<number | null>(null)
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')

  // Initial Snapshot for Dirty Tracking
  const [initialFieldValues, setInitialFieldValues] = useState<Record<string, string>>({})
  const [initialDeckId, setInitialDeckId] = useState<number | null>(null)
  const [initialTags, setInitialTags] = useState<string[]>([])

  // Debounce main search query
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(queryText.trim())
      setPage(1)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  // Decks Tree Query
  const decksQuery = useQuery({
    queryKey: ['browse', 'decks'],
    queryFn: () => appApi.get<{ decks: BrowseDeck[] }>('/browse/decks'),
  })

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
  })

  const cards = cardsQuery.data?.items || []

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

  // Populate editor state
  const ttsSourceFieldRef = useRef(ttsSourceField)
  ttsSourceFieldRef.current = ttsSourceField
  const ttsDestinationFieldRef = useRef(ttsDestinationField)
  ttsDestinationFieldRef.current = ttsDestinationField

  useEffect(() => {
    if (cardDetailQuery.data) {
      const fieldValues = cardDetailQuery.data.note.field_values || {}
      const deckId = cardDetailQuery.data.note.deck_id || null
      const tags = cardDetailQuery.data.note.tags || []

      setEditFieldValues(fieldValues)
      setEditDeckId(deckId)
      setEditTags(tags)

      setInitialFieldValues(fieldValues)
      setInitialDeckId(deckId)
      setInitialTags(tags)

      if (cardDetailQuery.data.fields && cardDetailQuery.data.fields.length > 0) {
        const fieldNames = cardDetailQuery.data.fields.map((f) => f.name)

        if (fieldNames.includes('Reading')) {
          setTtsSourceField('Reading')
        } else if (fieldNames.includes('Word')) {
          setTtsSourceField('Word')
        } else if (fieldNames.includes('Expression')) {
          setTtsSourceField('Expression')
        } else if (fieldNames.includes('Kanji')) {
          setTtsSourceField('Kanji')
        } else if (fieldNames.length > 0 && !fieldNames.includes(ttsSourceFieldRef.current)) {
          setTtsSourceField(fieldNames[0])
        }

        if (fieldNames.includes('Audio')) {
          setTtsDestinationField('Audio')
        } else if (fieldNames.includes('AudioReading')) {
          setTtsDestinationField('AudioReading')
        } else if (fieldNames.includes('Sound')) {
          setTtsDestinationField('Sound')
        } else if (fieldNames.length > 0 && !fieldNames.includes(ttsDestinationFieldRef.current)) {
          setTtsDestinationField(fieldNames[fieldNames.length - 1])
        }
      }
    }
  }, [cardDetailQuery.data])

  const isDirty = (() => {
    if (!activeCardId || !cardDetailQuery.data) return false
    if (editDeckId !== initialDeckId) return true
    if (JSON.stringify(editTags) !== JSON.stringify(initialTags)) return true
    const currentKeys = Object.keys(editFieldValues)
    const initialKeys = Object.keys(initialFieldValues)
    if (currentKeys.length !== initialKeys.length) return true
    for (const key of currentKeys) {
      if ((editFieldValues[key] || '') !== (initialFieldValues[key] || '')) return true
    }
    return false
  })()

  const handleRevert = () => {
    setEditFieldValues(initialFieldValues)
    setEditDeckId(initialDeckId)
    setEditTags(initialTags)
  }

  // Update Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { field_values: Record<string, string>; deck_id?: number; tags?: string[] }) =>
      appApi.mutate(`/browse/cards/${activeCardId}`, 'PATCH', payload),
    onSuccess: () => {
      if (urlDeckId) {
        toast.success('Đã lưu thay đổi thẻ.', {
          duration: 2000,
          action: {
            label: 'Quay lại bài học',
            onClick: () => navigate(`/study?deck_id=${urlDeckId}`),
          },
        })
      } else {
        toast.success('Đã lưu thay đổi thẻ.', { duration: 1200 })
      }
      setInitialFieldValues(editFieldValues)
      setInitialDeckId(editDeckId)
      setInitialTags(editTags)
      if (activeCardId) {
        void updateCardFieldValuesInSessions(activeCardId, editFieldValues)
      }
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', activeCardId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể lưu thay đổi', { description: error.message })
    },
  })

  // Single Delete Mutation
  const deleteMutation = useMutation({
    mutationFn: (cardId: string) => appApi.mutate(`/browse/cards/${cardId}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa thẻ.')
      setActiveCardId(null)
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
    },
    onError: (error: Error) => {
      toast.error('Không thể xóa thẻ', { description: error.message })
    },
  })

  // Bulk Delete Mutation
  const bulkDeleteMutation = useMutation({
    mutationFn: async (cardIds: string[]) => {
      const results = await Promise.allSettled(
        cardIds.map((id) => appApi.mutate(`/browse/cards/${id}`, 'DELETE')),
      )
      const failed = results.filter((r) => r.status === 'rejected')
      if (failed.length > 0) {
        throw new Error(`Có ${failed.length}/${cardIds.length} thẻ xóa không thành công.`)
      }
      return cardIds.length
    },
    onSuccess: (count) => {
      toast.success(`Đã xóa thành công ${count} thẻ đã chọn.`)
      if (activeCardId && selectedCards.includes(activeCardId)) {
        setActiveCardId(null)
      }
      setSelectedCards([])
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
    },
    onError: (error: Error) => {
      toast.error('Lỗi khi xóa hàng loạt', { description: error.message })
    },
  })

  const targetTtsCardIds = selectedCards.length > 0 ? selectedCards : activeCardId ? [activeCardId] : []

  // VoiceVox TTS Generate Mutation
  const generateTtsMutation = useMutation({
    mutationFn: (payload: {
      card_ids: string[]
      source_field: string
      destination_field: string
      character_id?: string
      api_key?: string
      append_audio?: boolean
      use_opus?: boolean
      settings?: Record<string, number>
    }) => appApi.mutate('/browse/voicevox/generate', 'POST', payload),
    onSuccess: () => {
      if (ttsApiKey.trim()) {
        void saveApiKeyIfValid(ttsApiKey, false)
      }
      toast.success(`Đã tạo âm thanh VoiceVox cho ${targetTtsCardIds.length} thẻ!`)
      setIsTtsModalOpen(false)
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      if (activeCardId) {
        void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', activeCardId] })
      }
    },
    onError: (error: Error) => {
      toast.error('Không thể tạo âm thanh VoiceVox', { description: error.message })
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
      if (showToast) {
        toast.success('Đã tự động lưu VoiceVox API Key cho các lần dùng sau!')
      }
    } catch {
      // ignore
    } finally {
      setIsSavingKey(false)
    }
  }

  // Dynamic fetch voices
  const ttsVoicesQuery = useQuery({
    queryKey: ['voicevox-voices', ttsApiKey],
    queryFn: () =>
      appApi.mutate<{ items: Array<{ id: string; label: string; speaker_name: string; style_name: string }> }>(
        '/api/tts/providers/voicevox/voices',
        'POST',
        { api_key: ttsApiKey || undefined },
      ),
    enabled: isTtsModalOpen,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  })

  // Preview VoiceVox
  const handlePreviewVoiceVox = async () => {
    const previewText = cards[0]?.word || cards[0]?.reading || 'こんにちは'
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
      toast.success('Đang phát nghe thử audio...')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Lỗi nghe thử audio'
      toast.error('Lỗi xem trước audio', { description: message })
    } finally {
      setIsPreviewing(false)
    }
  }

  // Reset VoiceVox Settings
  const handleResetTtsDefaults = () => {
    setTtsSourceField('Word')
    setTtsDestinationField('Audio')
    setTtsCharacter('')
    setTtsApiKey('')
    setTtsAppendAudio(false)
    setTtsUseOpus(false)
    setTtsVolumeScale(1.0)
    setTtsPitch(0.0)
    setTtsSpeed(1.0)
    setTtsIntonationScale(1.0)
    setTtsInitialSilence(0.1)
    setTtsFinalSilence(0.1)
    toast.info('Đã khôi phục thiết lập VoiceVox về mặc định.')
  }

  const allSelected =
    cards.length > 0 && cards.every((card) => selectedCards.includes(card.card_id))

  const handleToggleSelectAllCards = () => {
    if (allSelected) {
      setSelectedCards([])
    } else {
      setSelectedCards(cards.map((c) => c.card_id))
    }
  }

  const filteredDecks = (decksQuery.data?.decks || []).filter((deck) =>
    deck.name.toLowerCase().includes(deckSearch.trim().toLowerCase()),
  )

  const handleAddTag = () => {
    const tag = newTagInput.trim()
    if (tag && !editTags.includes(tag)) {
      setEditTags([...editTags, tag])
      setNewTagInput('')
    }
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setEditTags(editTags.filter((t) => t !== tagToRemove))
  }

  const handleResetDeckFilter = () => {
    setSelectedDeckId(null)
    setDeckSearch('')
    setPage(1)
  }

  const availableFieldNames = Array.from(
    new Set(
      (
        cardDetailQuery.data?.fields?.map((f) => f.name) || [
          'Word',
          'Reading',
          'Meaning',
          'Audio',
          'AudioReading',
        ]
      ).filter(Boolean),
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
    setSelectedDeckId,
    deckSearch,
    setDeckSearch,
    queryText,
    setQueryText,
    debouncedQuery,
    statusFilter,
    setStatusFilter,
    sortBy,
    setSortBy,
    sortDir,
    setSortDir,
    page,
    setPage,
    perPage,
    handlePerPageChange,
    selectedCards,
    setSelectedCards,
    isTtsModalOpen,
    setIsTtsModalOpen,
    isLocalAudioModalOpen,
    setIsLocalAudioModalOpen,
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
    allSelected,
    filteredDecks,
    availableFieldNames,
    targetTtsCardIds,
    decksQuery,
    cardsQuery,
    cardDetailQuery,
    ttsProfileQuery,
    ttsVoicesQuery,
    handleRevert,
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
  }
}

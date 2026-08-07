import { useEffect, useRef, useState } from 'react'
import {
  ArrowLeft,
  ArrowUpDown,
  BookOpen,
  Check,
  CheckSquare,
  ChevronDown,
  Eye,
  EyeOff,
  ExternalLink,
  FileText,
  FileUp,
  Folder,
  FolderOpen,
  HelpCircle,
  Layers,
  LoaderCircle,
  Play,
  Plus,
  RotateCcw,
  Save,
  Search,
  Sliders,
  Square,
  Tag,
  Trash2,
  Volume2,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'
import { apiBlob } from '@/shared/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import { cn } from '@/lib/utils'
import { Brand } from '@/shared/components/Brand'
import { PageError, PageLoading } from '@/shared/components/PageState'

type BrowseCardRow = {
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

type BrowseCardsResponse = {
  items: BrowseCardRow[]
  page: number
  total: number
  pages: number
  has_next: boolean
}

const FALLBACK_VOICEVOX_SPEAKERS = [
  { id: '3', label: 'Zundamon (ズンダモン - ノーマル)' },
  { id: '1', label: 'Zundamon (ズンダモン - あまあま)' },
  { id: '7', label: 'Zundamon (ズンダモン - ツンツン)' },
  { id: '5', label: 'Zundamon (ズンダモン - セクシー)' },
  { id: '22', label: 'Zundamon (ズンダモン - ささやき)' },
  { id: '38', label: 'Zundamon (ズンダモン - ヒソヒソ)' },
  { id: '2', label: 'Shikikoin Metan (四国めたん - ノーマル)' },
  { id: '0', label: 'Shikikoin Metan (四国めたん - あまあま)' },
  { id: '6', label: 'Shikikoin Metan (四国めたん - ツンツン)' },
  { id: '4', label: 'Shikikoin Metan (四国めたん - セクシー)' },
  { id: '36', label: 'Shikikoin Metan (四国めたん - ささやき)' },
  { id: '8', label: 'Kasukabe Tsumugi (春日部つむぎ - ノーマル)' },
  { id: '10', label: 'Namine Ritsu (波音リツ - ノーマル)' },
  { id: '9', label: 'Amehare Hare (雨晴はう - ノーマル)' },
  { id: '11', label: 'Kurono Takehiro (玄野武宏 - ノーマル)' },
  { id: '12', label: 'Shirakami Torataro (白上虎太郎 - ノーマル)' },
  { id: '13', label: 'Kyushu Sora (九州そら - ノーマル)' },
  { id: '14', label: 'Mochi-ko (もち子さん - ノーマル)' },
  { id: '15', label: 'Kenzaki Mesubuta (剣崎牝豹 - ノーマル)' },
  { id: '16', label: 'Aoyama Ryuusei (青山龍星 - ノーマル)' },
  { id: '20', label: 'WhiteCUL (WhiteCUL - ノーマル)' },
  { id: '21', label: 'WhiteCUL (WhiteCUL - たのしい)' },
  { id: '29', label: 'No.7 (No.7 - ノーマル)' },
  { id: '30', label: 'No.7 (No.7 - アナウンス)' },
  { id: '42', label: 'Chibi Shikijii (ちび式じい - ノーマル)' },
  { id: '54', label: 'Nurse Robot Type T (ナースロボ＿タイプＴ - ノーマル)' },
]

type BrowseDeck = {
  id: number
  name: string
  parent_id?: number | null
  counts?: {
    new?: number
    learn?: number
    due?: number
  }
}

type CardDetailField = {
  name: string
  position: number
  required?: boolean
}

type CardDetailResponse = {
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
  decks?: Array<{ id: number; name: string }>
}

function statusLabel(status: string) {
  if (status === 'new') return 'Mới'
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'Đang học'
  }
  if (status === 'due' || status === 'review') return 'Đến hạn'
  return status || 'Khác'
}

function statusVariant(status: string) {
  if (status === 'due' || status === 'review') return 'destructive' as const
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'outline' as const
  }
  return 'secondary' as const
}

export function BrowsePage() {
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

  // VoiceVox TTS Audio Generation Modal State (Matching Original Template)
  const [isTtsModalOpen, setIsTtsModalOpen] = useState(false)
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

  // Handle Keyboard Shortcuts (Ctrl+A / Cmd+A to select all cards, Escape to clear selection)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement
      const isEditingText =
        activeEl instanceof HTMLInputElement ||
        activeEl instanceof HTMLTextAreaElement ||
        Boolean((activeEl as HTMLElement | null)?.isContentEditable)

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        if (!isEditingText && cards.length > 0) {
          e.preventDefault()
          setSelectedCards(cards.map((c) => c.card_id))
        }
      } else if (e.key === 'Escape') {
        if (!isEditingText && selectedCards.length > 0) {
          e.preventDefault()
          setSelectedCards([])
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [cards, selectedCards.length])

  // Selected Card Detail Query
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', activeCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${activeCardId}`),
    enabled: Boolean(activeCardId),
  })

  // Populate editor state when detail query loads
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

      // Auto populate source & dest fields from available fields matching NoteType template
      if (cardDetailQuery.data.fields && cardDetailQuery.data.fields.length > 0) {
        const fieldNames = cardDetailQuery.data.fields.map((f) => f.name)

        // Best Source Field matching: Reading > Word > Expression > Kanji
        if (fieldNames.includes('Reading')) {
          setTtsSourceField('Reading')
        } else if (fieldNames.includes('Word')) {
          setTtsSourceField('Word')
        } else if (fieldNames.includes('Expression')) {
          setTtsSourceField('Expression')
        } else if (fieldNames.includes('Kanji')) {
          setTtsSourceField('Kanji')
        } else if (fieldNames.length > 0 && !fieldNames.includes(ttsSourceField)) {
          setTtsSourceField(fieldNames[0])
        }

        // Best Destination Field matching: Audio > AudioReading > Sound
        if (fieldNames.includes('Audio')) {
          setTtsDestinationField('Audio')
        } else if (fieldNames.includes('AudioReading')) {
          setTtsDestinationField('AudioReading')
        } else if (fieldNames.includes('Sound')) {
          setTtsDestinationField('Sound')
        } else if (fieldNames.length > 0 && !fieldNames.includes(ttsDestinationField)) {
          setTtsDestinationField(fieldNames[fieldNames.length - 1])
        }
      }
    }
  }, [cardDetailQuery.data])

  // Check if editor has unsaved changes
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

  // Reset form to initial snapshot
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

  // Bulk Delete Mutation over selectedCards
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

  // Target card IDs for VoiceVox Generation: Strictly target user-selected cards or active selected card
  const targetTtsCardIds =
    selectedCards.length > 0
      ? selectedCards
      : activeCardId
        ? [activeCardId]
        : []

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

  // Fetch user saved TTS profile for VoiceVox
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
      // LocalStorage is already saved as fallback
    } finally {
      setIsSavingKey(false)
    }
  }

  // Dynamic fetch VoiceVox voices from backend/API
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

  // VoiceVox TTS Preview Handler
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

  // Reset VoiceVox Settings to Default
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

  // Select all / Deselect all cards handler
  const handleToggleSelectAllCards = () => {
    if (allSelected) {
      setSelectedCards([])
    } else {
      setSelectedCards(cards.map((c) => c.card_id))
    }
  }

  // Filtered decks for sidebar
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

  // Reset deck filter
  const handleResetDeckFilter = () => {
    setSelectedDeckId(null)
    setDeckSearch('')
    setPage(1)
  }

  // Available Note Fields for Dropdown Selects (Deduplicated & Cleaned)
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

  return (
    <div className="flex flex-col h-screen h-[100dvh] w-full overflow-hidden bg-background text-foreground">
      {/* Hidden Audio Player for Preview */}
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Top Navbar Header for Fullscreen Browse */}
      <header className="sticky top-0 z-30 flex h-12 sm:h-14 shrink-0 items-center justify-between border-b border-border/60 bg-background/95 px-2.5 sm:px-4 backdrop-blur-md">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {urlDeckId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs font-bold text-primary border-primary/30 hover:bg-primary/10 rounded-full gap-1.5 px-3 shrink-0"
              onClick={() => navigate(`/study?deck_id=${urlDeckId}`)}
            >
              <ArrowLeft className="size-3.5" />
              <span>Quay lại bài học</span>
            </Button>
          ) : (
            <Brand compact size="sm" hideTextOnCollapse />
          )}
          <span className="hidden sm:inline text-xs sm:text-sm font-semibold text-foreground truncate">Duyệt thẻ</span>
        </div>

        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1"
              >
                <Volume2 className="size-3.5 text-primary" />
                <span className="hidden sm:inline">Tạo âm thanh</span>
                <ChevronDown className="size-3 opacity-60 ml-0.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  <span className="font-medium">Tiếng Nhật</span>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent className="w-48">
                  <DropdownMenuItem onClick={() => setIsTtsModalOpen(true)}>
                    <span className="font-medium text-foreground">Web VoiceVox</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem disabled className="flex items-center justify-between opacity-60">
                    <span>VoiceVox Local</span>
                    <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal">Sắp có</Badge>
                  </DropdownMenuItem>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  <span className="font-medium">Tiếng Anh</span>
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent className="w-48">
                  <DropdownMenuItem disabled className="flex items-center justify-between opacity-60">
                    <span>Tiếng Anh Local</span>
                    <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal">Sắp có</Badge>
                  </DropdownMenuItem>
                </DropdownMenuSubContent>
              </DropdownMenuSub>
            </DropdownMenuContent>
          </DropdownMenu>
          {isAdmin ? (
            <Button variant="outline" size="sm" asChild className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3">
              <a href="/flashcards/import">
                <FileUp className="size-3.5 sm:mr-1.5" />
                <span className="hidden sm:inline">Nhập CSV</span>
              </a>
            </Button>
          ) : null}
          <Button
            size="sm"
            asChild
            className="h-7 sm:h-8 rounded-full bg-gradient-to-r from-primary to-orange-500 text-primary-foreground font-bold shadow-xs text-[11px] sm:text-xs px-2.5 sm:px-3.5"
          >
            <a href="/flashcards/notes/new">
              <Plus className="size-3.5 sm:mr-1.5" />
              <span className="hidden sm:inline">Tạo ghi chú</span>
              <span className="sm:hidden">Tạo thẻ</span>
            </a>
          </Button>

          <Button
            variant="ghost"
            size="sm"
            className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 text-muted-foreground hover:text-foreground"
            onClick={() => {
              if (urlDeckId) {
                navigate(`/study?deck_id=${urlDeckId}`)
              } else {
                navigate('/dashboard')
              }
            }}
          >
            <ArrowLeft className="size-3.5" />
            <span className="hidden sm:inline">
              {urlDeckId ? 'Về bài học' : 'Tổng quan'}
            </span>
            <span className="sm:hidden">
              {urlDeckId ? 'Bài học' : 'Về'}
            </span>
          </Button>
        </div>
      </header>

      {/* Mobile Segmented Tab Bar (Appears on screens < lg) */}
      <div className="flex lg:hidden items-center justify-between px-2 py-1.5 border-b border-border/30 bg-background shrink-0">
        <div className="grid grid-cols-3 w-full p-1 bg-muted/70 rounded-xl gap-1">
          <button
            type="button"
            onClick={() => setMobileTab('decks')}
            className={cn(
              'flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200',
              mobileTab === 'decks'
                ? 'bg-background text-primary shadow-xs font-bold'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <FolderOpen className="size-3.5" />
            <span>Decks</span>
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('cards')}
            className={cn(
              'flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200',
              mobileTab === 'cards'
                ? 'bg-background text-primary shadow-xs font-bold'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <BookOpen className="size-3.5" />
            <span>Danh sách</span>
          </button>
          <button
            type="button"
            onClick={() => setMobileTab('editor')}
            className={cn(
              'flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg text-xs font-semibold transition-all duration-200',
              mobileTab === 'editor'
                ? 'bg-background text-primary shadow-xs font-bold'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <FileText className="size-3.5" />
            <span>Editor</span>
          </button>
        </div>
      </div>

      {/* 3-Pane Responsive Grid */}
      <div className="flex-1 min-h-0 grid gap-0 sm:gap-3 lg:grid-cols-12 p-0 sm:p-3 overflow-hidden">
        {/* ========================================================================= */}
        {/* LEFT PANE: DECKS SIDEBAR (3 cols on lg) */}
        {/* ========================================================================= */}
        <Card className={cn('lg:col-span-3 h-full flex flex-col border-0 sm:border border-border/80 shadow-none sm:shadow-md rounded-none sm:rounded-2xl overflow-hidden min-h-0', mobileTab !== 'decks' && 'hidden lg:flex')}>
          <div className="p-3 border-b bg-muted/30 flex items-center justify-between shrink-0">
            <h2 className="font-bold text-sm flex items-center gap-1.5">
              <FolderOpen className="size-4 text-primary" />
              Bộ thẻ (Decks)
            </h2>
            {selectedDeckId !== null ? (
              <button
                type="button"
                className="text-[10px] text-primary hover:underline font-semibold"
                onClick={handleResetDeckFilter}
              >
                Hủy chọn deck
              </button>
            ) : null}
          </div>

          <div className="p-2 border-b bg-muted/10 shrink-0">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                className="pl-8 pr-7 h-8 text-xs bg-background"
                placeholder="Lọc bộ thẻ…"
                value={deckSearch}
                onChange={(e) => setDeckSearch(e.target.value)}
              />
              {deckSearch ? (
                <button
                  type="button"
                  onClick={() => setDeckSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              ) : null}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1 min-h-0">
            {/* Shortcut: All Decks */}
            <button
              type="button"
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-semibold transition-colors ${
                selectedDeckId === null
                  ? 'bg-primary/15 text-primary border border-primary/30 shadow-xs'
                  : 'hover:bg-muted/60 text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => {
                handleResetDeckFilter()
                setMobileTab('cards')
              }}
            >
              <span className="flex items-center gap-2">
                <BookOpen className="size-4 shrink-0 text-primary" />
                <span>Tất cả deck</span>
              </span>
              <Badge variant="outline" className="text-[10px] font-mono">
                All
              </Badge>
            </button>

            {/* Deck List Tree */}
            {decksQuery.isPending ? (
              <div className="p-4 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <LoaderCircle className="size-4 animate-spin text-primary" />
                Đang tải danh sách deck…
              </div>
            ) : null}

            {filteredDecks.map((deck) => {
              const isSelected = selectedDeckId === deck.id
              const dueCount = deck.counts?.due || 0
              const newCount = deck.counts?.new || 0
              const learnCount = deck.counts?.learn || 0
              const totalDeckDue = dueCount + newCount + learnCount

              return (
                <button
                  key={deck.id}
                  type="button"
                  className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-colors ${
                    isSelected
                      ? 'bg-primary/15 text-primary font-bold border border-primary/30 shadow-xs'
                      : 'hover:bg-muted/50 text-foreground'
                  }`}
                  onClick={() => {
                    setSelectedDeckId(deck.id)
                    setPage(1)
                    setMobileTab('cards')
                  }}
                >
                  <span className="flex items-center gap-2 truncate pr-2">
                    {isSelected ? (
                      <FolderOpen className="size-3.5 shrink-0 text-primary" />
                    ) : (
                      <Folder className="size-3.5 shrink-0 text-muted-foreground" />
                    )}
                    <span className="truncate">{deck.name}</span>
                  </span>
                  {totalDeckDue > 0 ? (
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-mono">
                      {totalDeckDue}
                    </Badge>
                  ) : null}
                </button>
              )
            })}

            {!decksQuery.isPending && !filteredDecks.length ? (
              <p className="p-4 text-center text-xs text-muted-foreground">
                Không tìm thấy deck phù hợp.
              </p>
            ) : null}
          </div>
        </Card>

        {/* ========================================================================= */}
        {/* CENTER PANE: NOTES / CARDS TABLE (5 cols on lg) */}
        {/* ========================================================================= */}
        <Card className={cn('lg:col-span-5 h-full flex flex-col border-0 sm:border border-border/80 shadow-none sm:shadow-md rounded-none sm:rounded-2xl overflow-hidden min-h-0', mobileTab !== 'cards' && 'hidden lg:flex')}>
          {/* Main Toolbar */}
          <div className="p-2.5 sm:p-3 border-b bg-muted/30 space-y-2 shrink-0">
            <div className="flex flex-col sm:grid sm:grid-cols-12 gap-2 items-center">
              {/* Search Box */}
              <div className="w-full sm:col-span-6 relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="pl-8 pr-7 h-8 text-xs bg-background"
                  placeholder="Tìm từ, cách đọc, nghĩa..."
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                />
                {queryText ? (
                  <button
                    type="button"
                    onClick={() => setQueryText('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-3.5" />
                  </button>
                ) : null}
              </div>

              {/* Filters & Sorting */}
              <div className="flex items-center gap-1.5 w-full sm:col-span-6">
                <NativeSelect
                  className="h-8 text-xs bg-background flex-1"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value)
                    setPage(1)
                  }}
                >
                  <NativeSelectOption value="all">Tất cả trạng thái</NativeSelectOption>
                  <NativeSelectOption value="new">Mới (New)</NativeSelectOption>
                  <NativeSelectOption value="learn">Đang học (Learn)</NativeSelectOption>
                  <NativeSelectOption value="due">Đến hạn (Due)</NativeSelectOption>
                </NativeSelect>

                <NativeSelect
                  className="h-8 text-xs bg-background flex-1"
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                >
                  <NativeSelectOption value="due">Đến hạn</NativeSelectOption>
                  <NativeSelectOption value="deck">Deck</NativeSelectOption>
                  <NativeSelectOption value="word">Từ vựng</NativeSelectOption>
                </NativeSelect>

                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 shrink-0 bg-background"
                  title={sortDir === 'asc' ? 'Tăng dần' : 'Giảm dần'}
                  onClick={() => setSortDir(sortDir === 'asc' ? 'desc' : 'asc')}
                >
                  <ArrowUpDown className="size-3.5" />
                </Button>
              </div>
            </div>

            {/* Bulk Selection Actions Toolbar (Appears when cards are selected) */}
            {selectedCards.length > 0 ? (
              <div className="flex flex-wrap items-center justify-between gap-2 p-1.5 rounded-lg bg-primary/10 border border-primary/20 text-xs animate-in fade-in duration-150">
                <div className="flex items-center gap-1.5">
                  <Badge variant="default" className="text-[10px] font-bold">
                    Đã chọn {selectedCards.length} từ
                  </Badge>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-6 text-[11px] px-2 text-primary hover:bg-primary/20"
                    onClick={handleToggleSelectAllCards}
                  >
                    {allSelected ? (
                      <>
                        <Square className="size-3 mr-1" /> Bỏ chọn tất cả
                      </>
                    ) : (
                      <>
                        <CheckSquare className="size-3 mr-1" /> Chọn tất cả {cards.length} từ
                      </>
                    )}
                  </Button>
                </div>

                <div className="flex items-center gap-1.5">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-6 text-[11px] px-2 gap-1"
                      >
                        <Volume2 className="size-3 text-primary" />
                        <span>Tạo âm thanh ({selectedCards.length})</span>
                        <ChevronDown className="size-3 opacity-60 ml-0.5" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="w-52">
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger>
                          <span className="font-medium">Tiếng Nhật</span>
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent className="w-48">
                          <DropdownMenuItem onClick={() => setIsTtsModalOpen(true)}>
                            <span className="font-medium text-foreground">Web VoiceVox</span>
                          </DropdownMenuItem>
                          <DropdownMenuItem disabled className="flex items-center justify-between opacity-60">
                            <span>VoiceVox Local</span>
                            <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal">Sắp có</Badge>
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger>
                          <span className="font-medium">Tiếng Anh</span>
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent className="w-48">
                          <DropdownMenuItem disabled className="flex items-center justify-between opacity-60">
                            <span>Tiếng Anh Local</span>
                            <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal">Sắp có</Badge>
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    className="h-6 text-[11px] px-2.5 font-bold shadow-xs"
                    disabled={bulkDeleteMutation.isPending}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Bạn có chắc chắn muốn xóa vĩnh viễn ${selectedCards.length} thẻ đã chọn?`,
                        )
                      ) {
                        bulkDeleteMutation.mutate(selectedCards)
                      }
                    }}
                  >
                    {bulkDeleteMutation.isPending ? (
                      <LoaderCircle className="size-3 animate-spin mr-1" />
                    ) : (
                      <Trash2 className="size-3 mr-1" />
                    )}
                    Xóa {selectedCards.length} thẻ
                  </Button>
                </div>
              </div>
            ) : null}
          </div>

          {/* Cards Table Container */}
          <div className="flex-1 overflow-auto min-h-0">
            {cardsQuery.isPending ? <PageLoading label="Đang tải thẻ…" /> : null}
            {cardsQuery.error ? <PageError error={cardsQuery.error} /> : null}

            {cardsQuery.data ? (
              <table className="w-full text-xs text-left border-collapse min-w-[500px]">
                <thead className="sticky top-0 bg-muted/90 backdrop-blur-sm z-10 border-b shadow-xs">
                  <tr>
                    <th className="p-2.5 w-8">
                      <Checkbox
                        checked={
                          allSelected ? true : selectedCards.length > 0 ? 'indeterminate' : false
                        }
                        onCheckedChange={handleToggleSelectAllCards}
                        aria-label="Chọn tất cả từ"
                      />
                    </th>
                    <th className="p-2.5 font-bold">Từ vựng</th>
                    <th className="p-2.5 font-bold">Cách đọc</th>
                    <th className="p-2.5 font-bold">Nghĩa</th>
                    <th className="p-2.5 font-bold">Deck</th>
                    <th className="p-2.5 font-bold">Trạng thái</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {cards.map((card) => {
                    const isSelected = activeCardId === card.card_id
                    const isChecked = selectedCards.includes(card.card_id)
                    return (
                      <tr
                        key={card.card_id}
                        onClick={() => {
                          setActiveCardId(card.card_id)
                          setMobileTab('editor')
                        }}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-primary/15 font-semibold text-primary'
                            : isChecked
                              ? 'bg-muted/60'
                              : 'hover:bg-muted/50'
                        }`}
                      >
                        <td className="p-2.5" onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={isChecked}
                            onCheckedChange={(checked) =>
                              setSelectedCards((current) =>
                                checked
                                  ? Array.from(new Set([...current, card.card_id]))
                                  : current.filter((id) => id !== card.card_id),
                              )
                            }
                            aria-label={`Chọn ${card.word}`}
                          />
                        </td>
                        <td className="p-2.5 font-bold text-foreground max-w-[120px] truncate">
                          {card.word || '(trống)'}
                        </td>
                        <td className="p-2.5 text-muted-foreground max-w-[100px] truncate">
                          {card.reading || '—'}
                        </td>
                        <td className="p-2.5 max-w-[140px] truncate">{card.meaning || '—'}</td>
                        <td className="p-2.5 text-muted-foreground max-w-[100px] truncate">
                          {card.deck_name}
                        </td>
                        <td className="p-2.5">
                          <Badge
                            variant={statusVariant(card.status)}
                            className="text-[10px] px-1.5 py-0"
                          >
                            {statusLabel(card.status)}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                  {!cards.length ? (
                    <tr>
                      <td colSpan={6} className="h-32 text-center text-muted-foreground">
                        Không tìm thấy thẻ nào phù hợp.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            ) : null}
          </div>

          {/* Table Footer & Pagination */}
          {cardsQuery.data ? (
            <div className="p-2.5 border-t bg-muted/20 flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground shrink-0">
              <div className="flex items-center gap-3">
                <span>
                  Tổng <strong className="text-foreground">{cardsQuery.data.total}</strong> thẻ
                  {selectedCards.length > 0 ? (
                    <span className="ml-1 text-primary font-bold">
                      (Đã chọn {selectedCards.length})
                    </span>
                  ) : null}
                </span>

                <div className="flex items-center gap-1.5 border-l border-border/60 pl-3">
                  <span className="text-[11px] text-muted-foreground whitespace-nowrap">Hiển thị:</span>
                  <NativeSelect
                    className="h-7 text-xs bg-background w-auto min-w-[85px] px-2 py-0"
                    value={perPage}
                    onChange={(e) => handlePerPageChange(Number(e.target.value))}
                  >
                    <NativeSelectOption value={20}>20 / trang</NativeSelectOption>
                    <NativeSelectOption value={50}>50 / trang</NativeSelectOption>
                    <NativeSelectOption value={100}>100 / trang</NativeSelectOption>
                    <NativeSelectOption value={200}>200 / trang</NativeSelectOption>
                    <NativeSelectOption value={500}>500 / trang</NativeSelectOption>
                  </NativeSelect>
                </div>
              </div>
              {cardsQuery.data.pages > 1 ? (
                <Pagination className="mx-0 w-auto shrink-0">
                  <PaginationContent className="gap-1">
                    <PaginationItem>
                      <PaginationPrevious
                        href="#"
                        text="Trước"
                        aria-disabled={page <= 1}
                        className={cn(page <= 1 && 'opacity-40 pointer-events-none')}
                        onClick={(e) => {
                          e.preventDefault()
                          if (page > 1) setPage((p) => p - 1)
                        }}
                      />
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationLink
                        href="#"
                        isActive
                        className="px-2.5 min-w-[3rem] font-mono text-xs font-bold"
                        onClick={(e) => e.preventDefault()}
                      >
                        {page} / {cardsQuery.data.pages}
                      </PaginationLink>
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationNext
                        href="#"
                        text="Sau"
                        aria-disabled={!cardsQuery.data.has_next}
                        className={cn(!cardsQuery.data.has_next && 'opacity-40 pointer-events-none')}
                        onClick={(e) => {
                          e.preventDefault()
                          if (cardsQuery.data.has_next) setPage((p) => p + 1)
                        }}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              ) : null}
            </div>
          ) : null}
        </Card>

        {/* ========================================================================= */}
        {/* RIGHT PANE: EDITOR PANEL (4 cols on lg) */}
        {/* ========================================================================= */}
        <Card className={cn('lg:col-span-4 h-full flex flex-col border-0 sm:border border-border/80 shadow-none sm:shadow-md rounded-none sm:rounded-2xl overflow-hidden min-h-0', mobileTab !== 'editor' && 'hidden lg:flex')}>
          {/* Editor Header Toolbar */}
          <div className="p-2.5 sm:p-3 border-b bg-muted/30 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="lg:hidden h-7 text-xs px-2 text-muted-foreground hover:text-foreground"
                onClick={() => setMobileTab('cards')}
              >
                <ArrowLeft className="size-3.5 mr-1" />
                Danh sách
              </Button>
              <h2 className="font-bold text-sm flex items-center gap-1.5">
                <FileText className="size-4 text-primary" />
                Editor Ghi chú
              </h2>
            </div>
            {activeCardId && cardDetailQuery.data ? (
              <div className="flex items-center gap-1.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs px-2"
                  disabled={!isDirty}
                  onClick={handleRevert}
                  title="Khôi phục lại dữ liệu chưa lưu"
                >
                  <RotateCcw className="size-3 mr-1" />
                  Khôi phục
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="h-7 text-xs px-2.5 bg-gradient-to-r from-primary to-orange-500 text-primary-foreground font-bold shadow-sm"
                  disabled={!isDirty || updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      field_values: editFieldValues,
                      deck_id: editDeckId || undefined,
                      tags: editTags,
                    })
                  }
                >
                  {updateMutation.isPending ? (
                    <LoaderCircle className="size-3 animate-spin" />
                  ) : (
                    <>
                      <Save className="size-3 mr-1" />
                      Lưu
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  className="h-7 text-xs px-2"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (window.confirm('Bạn có chắc chắn muốn xóa thẻ này?')) {
                      deleteMutation.mutate(activeCardId)
                    }
                  }}
                  title="Xóa thẻ"
                >
                  <Trash2 className="size-3" />
                </Button>
              </div>
            ) : null}
          </div>

          {/* Editor Content Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
            {!activeCardId ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-muted-foreground space-y-2">
                <FileText className="size-10 text-muted-foreground/40" />
                <p className="font-semibold text-sm text-foreground">Chưa chọn thẻ nào</p>
                <p className="text-xs">
                  Vui lòng nhấp vào một thẻ ở danh sách bên trái để xem và chỉnh sửa chi tiết các trường.
                </p>
              </div>
            ) : cardDetailQuery.isPending ? (
              <div className="h-full flex items-center justify-center p-8">
                <LoaderCircle className="size-6 animate-spin text-primary" />
              </div>
            ) : cardDetailQuery.data ? (
              <div className="space-y-4">
                {/* Deck Select with NoteType Tag */}
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="editor-deck-select" className="text-xs font-semibold">
                      Bộ thẻ (Deck)
                    </Label>
                    {cardDetailQuery.data.note.note_type_id ? (
                      <Link
                        to={`/note-types/${cardDetailQuery.data.note.note_type_id}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:text-primary/90 bg-primary/10 hover:bg-primary/15 px-2 py-0.5 rounded-md transition-colors"
                        title="Bấm để chỉnh sửa Live Template của loại thẻ này"
                      >
                        <Layers className="size-3" />
                        <span>{cardDetailQuery.data.note.note_type_name || 'NoteType'}</span>
                        <ExternalLink className="size-2.5 opacity-70" />
                      </Link>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted px-2 py-0.5 rounded-md">
                        <Layers className="size-3" />
                        <span>{cardDetailQuery.data.note.note_type_name || 'NoteType'}</span>
                      </span>
                    )}
                  </div>
                  <NativeSelect
                    id="editor-deck-select"
                    className="w-full text-xs"
                    value={editDeckId || ''}
                    onChange={(e) => setEditDeckId(Number(e.target.value))}
                  >
                    {(cardDetailQuery.data.decks || []).map((d) => (
                      <NativeSelectOption key={d.id} value={d.id}>
                        {d.name}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </div>

                {/* Dynamic Note Fields */}
                <div className="space-y-3 pt-2 border-t">
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                    Trường thông tin (Note Fields)
                  </h3>
                  {cardDetailQuery.data.fields.map((field) => (
                    <div key={field.name} className="space-y-1">
                      <Label
                        htmlFor={`editor-field-${field.name}`}
                        className="text-xs font-medium flex items-center justify-between"
                      >
                        <span>
                          {field.name}{' '}
                          {field.required ? <span className="text-destructive">*</span> : null}
                        </span>
                      </Label>
                      <textarea
                        id={`editor-field-${field.name}`}
                        rows={2}
                        className="w-full p-2 text-xs border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all resize-y"
                        value={editFieldValues[field.name] || ''}
                        onChange={(e) =>
                          setEditFieldValues({
                            ...editFieldValues,
                            [field.name]: e.target.value,
                          })
                        }
                      />
                    </div>
                  ))}
                </div>

                {/* Tags Manager */}
                <div className="space-y-2 pt-2 border-t">
                  <Label className="text-xs font-semibold">Thẻ phân loại (Tags)</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {editTags.map((tag) => (
                      <Badge
                        key={tag}
                        variant="secondary"
                        className="gap-1 rounded-full px-2 py-0.5 text-[11px]"
                      >
                        <Tag className="size-3 text-primary" />
                        <span>{tag}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveTag(tag)}
                          className="ml-0.5 text-muted-foreground hover:text-foreground"
                        >
                          <X className="size-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                  <div className="flex gap-1.5 pt-1">
                    <Input
                      className="h-8 text-xs"
                      placeholder="Thêm tag mới…"
                      value={newTagInput}
                      onChange={(e) => setNewTagInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault()
                          handleAddTag()
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={handleAddTag}
                    >
                      Thêm
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      {/* ========================================================================= */}
      {/* FULL VOICEVOX / TTS AUDIO GENERATION DIALOG MODAL (OPTIMIZED UI/UX) */}
      {/* ========================================================================= */}
      <Dialog open={isTtsModalOpen} onOpenChange={setIsTtsModalOpen}>
        <DialogContent className="w-[95vw] sm:max-w-3xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-xl sm:rounded-2xl border-border/60 shadow-2xl">
          {/* Modal Header */}
          <DialogHeader className="px-3.5 sm:px-6 py-3 sm:py-4 border-b bg-muted/20 shrink-0 text-left">
            <div className="flex items-center justify-between gap-2">
              <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
                <Volume2 className="size-4 sm:size-5 text-primary shrink-0" />
                <span>Tạo âm thanh &gt; Tiếng Nhật &gt; Web VoiceVox</span>
              </DialogTitle>
              <Badge variant="outline" className="text-[11px] sm:text-xs font-semibold bg-primary/10 text-primary border-primary/20 px-2 py-0.5 shrink-0">
                {targetTtsCardIds.length} thẻ
              </Badge>
            </div>
            <DialogDescription className="text-xs text-muted-foreground mt-1">
              Tự động tổng hợp phát âm VoiceVox tiếng Nhật cho các thẻ từ vựng đã chọn.
            </DialogDescription>
          </DialogHeader>

          {/* Modal Body Scrollable */}
          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 text-xs min-h-0">
            {/* Target Card Banner */}
            <div className="p-4 rounded-xl bg-muted/40 border border-border/60 flex items-center justify-between shadow-xs">
              <span className="font-semibold text-foreground text-xs">
                Phạm vi áp dụng:{' '}
                <strong className="text-primary font-bold ml-1">
                  {selectedCards.length > 0
                    ? `${selectedCards.length} thẻ đã tick chọn`
                    : activeCardId
                      ? '1 thẻ đang chọn trong bảng'
                      : 'Chưa chọn thẻ nào trong bảng'}
                </strong>
              </span>
              <Badge
                variant={targetTtsCardIds.length > 0 ? 'default' : 'destructive'}
                className="text-[11px] px-2.5 py-0.5"
              >
                {selectedCards.length > 0
                  ? `${selectedCards.length} thẻ`
                  : activeCardId
                    ? '1 thẻ'
                    : 'Chưa chọn'}
              </Badge>
            </div>

            {/* Source & Destination Fields Row */}
            <div className="space-y-2">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="voicevox-source" className="text-xs font-semibold text-foreground">
                    Trường nguồn đọc (Source Field)
                  </Label>
                  <NativeSelect
                    id="voicevox-source"
                    className="w-full h-9 text-xs bg-background"
                    value={ttsSourceField}
                    onChange={(e) => setTtsSourceField(e.target.value)}
                  >
                    {availableFieldNames.map((fn) => (
                      <NativeSelectOption key={`src-${fn}`} value={fn}>
                        {fn} {fn === 'Reading' ? '(Khuyên dùng cho JP)' : ''}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="voicevox-dest" className="text-xs font-semibold text-foreground">
                    Trường đích lưu Audio (Destination Field)
                  </Label>
                  <NativeSelect
                    id="voicevox-dest"
                    className="w-full h-9 text-xs bg-background"
                    value={ttsDestinationField}
                    onChange={(e) => setTtsDestinationField(e.target.value)}
                  >
                    {availableFieldNames.map((fn) => (
                      <NativeSelectOption key={`dst-${fn}`} value={fn}>
                        {fn} {fn === 'Audio' ? '(Mặc định lưu file)' : ''}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                </div>
              </div>

              {cardDetailQuery.data?.note?.note_type_name ? (
                <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                  <span className="flex items-center gap-1">
                    <Layers className="size-3 text-primary shrink-0" />
                    <span>
                      Đang khớp các trường theo loại thẻ: <strong className="text-foreground">{cardDetailQuery.data.note.note_type_name}</strong>
                    </span>
                  </span>
                  {ttsSourceField === ttsDestinationField ? (
                    <span className="text-amber-600 dark:text-amber-400 font-semibold">
                      ⚠️ Trường nguồn và trường đích đang giống nhau
                    </span>
                  ) : null}
                </div>
              ) : null}
            </div>

            {/* Character & API Key Row */}
            <div className="grid gap-4 sm:grid-cols-2 pt-4 border-t border-border/40">
              <div className="space-y-1.5">
                <Label htmlFor="voicevox-character" className="text-xs font-semibold text-foreground">
                  Nhân vật / Giọng đọc
                </Label>
                <NativeSelect
                  id="voicevox-character"
                  className="w-full h-9 text-xs bg-background"
                  value={ttsCharacter}
                  onChange={(e) => setTtsCharacter(e.target.value)}
                >
                  <NativeSelectOption value="">Mặc định (Default Speaker)</NativeSelectOption>
                  {ttsVoicesQuery.isLoading ? (
                    <NativeSelectOption value="" disabled>
                      Đang tải danh sách giọng đọc...
                    </NativeSelectOption>
                  ) : ttsVoicesQuery.data?.items && ttsVoicesQuery.data.items.length > 0 ? (
                    ttsVoicesQuery.data.items.map((voice) => (
                      <NativeSelectOption key={voice.id} value={voice.id}>
                        {voice.label}
                      </NativeSelectOption>
                    ))
                  ) : (
                    FALLBACK_VOICEVOX_SPEAKERS.map((voice) => (
                      <NativeSelectOption key={voice.id} value={voice.id}>
                        {voice.label}
                      </NativeSelectOption>
                    ))
                  )}
                </NativeSelect>
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="voicevox-api-key" className="text-xs font-semibold text-foreground">
                    VoiceVox API Key (Tự động lưu)
                  </Label>
                  {isKeySaved ? (
                    <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] py-0 h-4">
                      ✓ Đã lưu Key
                    </Badge>
                  ) : null}
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="relative flex-1 flex items-center">
                    <Input
                      id="voicevox-api-key"
                      type={showApiKey ? 'text' : 'password'}
                      className="h-9 text-xs pr-9 bg-background"
                      placeholder="Mặc định theo hệ thống"
                      value={ttsApiKey}
                      onChange={(e) => {
                        setTtsApiKey(e.target.value)
                        setIsKeySaved(false)
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-2.5 text-muted-foreground hover:text-foreground transition-colors"
                      title={showApiKey ? 'Ẩn API key' : 'Hiện API key'}
                    >
                      {showApiKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-9 text-xs px-3 shrink-0"
                    disabled={isSavingKey || !ttsApiKey.trim()}
                    onClick={() => saveApiKeyIfValid(ttsApiKey, true)}
                  >
                    {isSavingKey ? (
                      <LoaderCircle className="size-3.5 animate-spin" />
                    ) : isKeySaved ? (
                      <>
                        <Check className="size-3.5 text-emerald-500" />
                        <span>Đã lưu</span>
                      </>
                    ) : (
                      <>
                        <Save className="size-3.5 text-primary" />
                        <span>Lưu Key</span>
                      </>
                    )}
                  </Button>
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                  <span className="flex items-center gap-1">
                    <HelpCircle className="size-3 text-primary shrink-0" />
                    <Link to="/guide/tts-key" target="_blank" rel="noopener noreferrer" className="font-medium text-primary underline hover:text-primary/80">
                      Hướng dẫn lấy Key VoiceVox
                    </Link>
                  </span>
                  <a href="https://su-shiki.com/api/" target="_blank" rel="noopener noreferrer" className="hover:underline flex items-center gap-0.5">
                    <span>su-shiki.com</span>
                    <ExternalLink className="size-2.5" />
                  </a>
                </div>
              </div>
            </div>

            {/* Checkboxes Row */}
            <div className="flex flex-wrap items-center gap-6 pt-4 border-t border-border/40">
              <div className="flex items-center space-x-2.5">
                <Checkbox
                  id="voicevox-append-audio"
                  checked={ttsAppendAudio}
                  onCheckedChange={(checked) => setTtsAppendAudio(Boolean(checked))}
                />
                <Label htmlFor="voicevox-append-audio" className="text-xs cursor-pointer font-medium text-foreground">
                  Nối thêm audio vào trường hiện có
                </Label>
              </div>

              <div className="flex items-center space-x-2.5">
                <Checkbox
                  id="voicevox-use-opus"
                  checked={ttsUseOpus}
                  onCheckedChange={(checked) => setTtsUseOpus(Boolean(checked))}
                />
                <Label htmlFor="voicevox-use-opus" className="text-xs cursor-pointer font-medium text-foreground">
                  Dùng format opus thay cho mp3
                </Label>
              </div>
            </div>

            {/* Advanced Audio Sliders (Sleek Card Container) */}
            <div className="space-y-3 pt-4 border-t border-border/40">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-xs flex items-center gap-2 text-foreground">
                  <Sliders className="size-4 text-primary" />
                  Cấu hình âm thanh nâng cao
                </h4>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 text-[11px] text-muted-foreground hover:text-foreground gap-1.5"
                  onClick={handleResetTtsDefaults}
                >
                  <RotateCcw className="size-3" /> Khôi phục mặc định
                </Button>
              </div>

              <div className="grid gap-3.5 sm:grid-cols-2 pt-1">
                {/* Volume Scale */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Âm lượng</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsVolumeScale.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsVolumeScale}
                    onChange={(e) => setTtsVolumeScale(parseFloat(e.target.value))}
                  />
                </div>

                {/* Pitch */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Cao độ</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsPitch.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="-0.4"
                    max="0.4"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsPitch}
                    onChange={(e) => setTtsPitch(parseFloat(e.target.value))}
                  />
                </div>

                {/* Speed */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Tốc độ đọc</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsSpeed.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="4"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsSpeed}
                    onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
                  />
                </div>

                {/* Intonation */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Ngữ điệu</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsIntonationScale.toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsIntonationScale}
                    onChange={(e) => setTtsIntonationScale(parseFloat(e.target.value))}
                  />
                </div>

                {/* Initial Silence */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Khoảng lặng đầu</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsInitialSilence.toFixed(2)}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsInitialSilence}
                    onChange={(e) => setTtsInitialSilence(parseFloat(e.target.value))}
                  />
                </div>

                {/* Final Silence */}
                <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                  <div className="flex items-center justify-between text-xs font-medium text-foreground">
                    <span>Khoảng lặng cuối</span>
                    <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                      {ttsFinalSilence.toFixed(2)}s
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.01"
                    className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                    value={ttsFinalSilence}
                    onChange={(e) => setTtsFinalSilence(parseFloat(e.target.value))}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Modal Footer Actions */}
          <DialogFooter className="px-6 pt-5 pb-6 sm:pb-7 border-t bg-muted/20 gap-3 sm:justify-between items-center shrink-0">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 text-xs gap-1.5 rounded-lg font-semibold"
              disabled={isPreviewing}
              onClick={handlePreviewVoiceVox}
            >
              {isPreviewing ? (
                <LoaderCircle className="size-4 animate-spin" />
              ) : (
                <Play className="size-4 text-primary" />
              )}
              Nghe thử giọng đọc
            </Button>

            <div className="flex items-center gap-2.5">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 text-xs rounded-lg px-4"
                onClick={() => setIsTtsModalOpen(false)}
              >
                Đóng
              </Button>
              <Button
                type="button"
                size="sm"
                className="h-9 text-xs bg-gradient-to-r from-primary via-orange-500 to-amber-500 font-bold shadow-md shadow-primary/20 hover:opacity-95 rounded-lg px-5"
                disabled={generateTtsMutation.isPending || targetTtsCardIds.length === 0}
                onClick={() =>
                  generateTtsMutation.mutate({
                    card_ids: targetTtsCardIds,
                    source_field: ttsSourceField.trim(),
                    destination_field: ttsDestinationField.trim(),
                    character_id: ttsCharacter || undefined,
                    api_key: ttsApiKey || undefined,
                    append_audio: ttsAppendAudio,
                    use_opus: ttsUseOpus,
                    settings: {
                      volume_scale: ttsVolumeScale,
                      pitch: ttsPitch,
                      speed_scale: ttsSpeed,
                      intonation_scale: ttsIntonationScale,
                      initial_silence: ttsInitialSilence,
                      final_silence: ttsFinalSilence,
                    },
                  })
                }
              >
                {generateTtsMutation.isPending ? (
                  <LoaderCircle className="size-4 animate-spin mr-1.5" />
                ) : (
                  <Volume2 className="size-4 mr-1.5" />
                )}
                Tạo audio ({targetTtsCardIds.length} thẻ)
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

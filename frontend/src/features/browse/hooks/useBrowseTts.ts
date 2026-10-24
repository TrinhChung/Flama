import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { fieldValueEditorText } from '@/entities/flashcard/fields'
import { cleanTextForTts } from '@/entities/audio'
import { browseApi } from '../api/browseApi'
import { browseQueryKeys } from '../api/browseQueryKeys'
import { useBrowseTtsSettings } from './useBrowseTtsSettings'
import type { useBrowseData } from './useBrowseData'
import type { useBrowseEditor } from './useBrowseEditor'
import type { useBrowseSelection } from './useBrowseSelection'
import type { useBrowseToolDialogs } from './useBrowseToolDialogs'

type BrowseTtsOptions = {
  data: ReturnType<typeof useBrowseData>
  editor: ReturnType<typeof useBrowseEditor>
  selection: ReturnType<typeof useBrowseSelection>
  dialogs: ReturnType<typeof useBrowseToolDialogs>
}

export function useBrowseTts({ data, editor, selection, dialogs }: BrowseTtsOptions) {
  const { t } = useTranslation('browse')
  const queryClient = useQueryClient()
  const { cards } = data
  const { activeCardId, cardDetailQuery } = editor
  const { selectedCards } = selection
  const { isLocalAudioModalOpen } = dialogs
  const [isTtsModalOpen, setIsTtsModalOpen] = useState(false)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)
  // Sample card detail query when no card is actively selected but modal is open
  const sampleCardId = activeCardId || (cards.length > 0 ? String(cards[0].card_id) : null)
  const deckSampleQuery = useQuery({
    queryKey: browseQueryKeys.detail(sampleCardId),
    queryFn: ({ signal }) => browseApi.fetchCardDetail(sampleCardId!, signal),
    enabled: Boolean(!activeCardId && sampleCardId && (isTtsModalOpen || isLocalAudioModalOpen)),
    staleTime: 5 * 60 * 1000,
  })

  const effectiveCardDetail = cardDetailQuery.data || deckSampleQuery.data


  const settings = useBrowseTtsSettings(effectiveCardDetail)
  const { ttsSourceField, ttsCharacter, ttsApiKey, setIsKeySaved, setIsSavingKey, ttsUseOpus, ttsVolumeScale, ttsPitch, ttsSpeed, ttsIntonationScale, ttsInitialSilence, ttsFinalSilence } = settings
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
    }) => browseApi.generateVoiceVox(payload),
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
    queryFn: ({ signal }) => browseApi.fetchVoiceVoxProfile(signal),
    enabled: isTtsModalOpen,
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (ttsProfileQuery.data?.profile?.has_api_key) {
      setIsKeySaved(true)
    }
  }, [ttsProfileQuery.data, setIsKeySaved])

  const saveApiKeyIfValid = async (keyToSave: string, showToast = true) => {
    const trimmed = keyToSave.trim()
    if (!trimmed) return
    setIsSavingKey(true)
    localStorage.setItem('flama_voicevox_api_key', trimmed)
    try {
      await browseApi.saveVoiceVoxProfile({
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
    queryFn: () => browseApi.fetchVoiceVoxVoices(ttsApiKeyRef.current || undefined),
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
      const blob = await browseApi.previewVoiceVox({
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


  return { ...settings, audioPlayerRef, isTtsModalOpen, setIsTtsModalOpen, isPreviewing, targetTtsCardIds, generateTtsMutation, ttsProfileQuery, ttsVoicesQuery, saveApiKeyIfValid, handlePreviewVoiceVox, availableSourceFieldNames, availableAudioFieldNames }
}

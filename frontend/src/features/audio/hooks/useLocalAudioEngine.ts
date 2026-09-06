import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { apiRequest } from '@/shared/api/client'
import {
  uploadNoteMediaBlob,
  uploadNoteMediaBatch,
  type BatchMediaItemInput,
} from '@/shared/api/noteMedia'
import {
  getLanguageGroupFromVoiceId,
  loadStoredLocalAudioSettings,
  saveStoredLocalAudioSettings,
  type LocalAudioSettings,
} from '../services/localAudioStorage'
import { scanDeckAudio } from '../services/audioScanService'
import { cleanTextForTts } from '../services/ttsTextNormalizer'
import type { VoiceDescriptor, DeckScanResponse } from '../types'

export type ProcessItemStatus = 'pending' | 'synthesizing' | 'uploading' | 'done' | 'failed' | 'skipped'

export type BatchItem = {
  cardId: string
  noteId: string
  word: string
  sourceText: string
  status: ProcessItemStatus
  error?: string
}

export type VoiceOption = {
  id: string
  speakerName: string
  styleName: string
  label: string
}

const FALLBACK_VOICEVOX_SPEAKERS: VoiceOption[] = [
  { id: '3', speakerName: 'ズンダモン (Zundamon)', styleName: 'ノーマル', label: 'ズンダモン (Zundamon) - ノーマル' },
  { id: '1', speakerName: 'ズンダモン (Zundamon)', styleName: 'あまあま', label: 'ズンダモン (Zundamon) - あまあま' },
  { id: '7', speakerName: 'ズンダモン (Zundamon)', styleName: 'ツンツン', label: 'ズンダモン (Zundamon) - ツンツン' },
  { id: '5', speakerName: 'ズンダモン (Zundamon)', styleName: 'セクシー', label: 'ズンダモン (Zundamon) - セクシー' },
  { id: '22', speakerName: 'ズンダモン (Zundamon)', styleName: 'ささやき', label: 'ズンダモン (Zundamon) - ささやき' },
  { id: '38', speakerName: 'ズンダモン (Zundamon)', styleName: 'ヒソヒソ', label: 'ズンダモン (Zundamon) - ヒソヒソ' },
  { id: '2', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'ノーマル', label: '四国めたん (Metan) - ノーマル' },
  { id: '0', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'あまあま', label: '四国めたん (Metan) - あまあま' },
  { id: '6', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'ツンツン', label: '四国めたん (Metan) - ツンツン' },
  { id: '4', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'セクシー', label: '四国めたん (Metan) - -セクシー' },
  { id: '36', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'ささやき', label: '四国めたん (Metan) - ささやき' },
  { id: '8', speakerName: '春日部つむぎ (Kasukabe Tsumugi)', styleName: 'ノーマル', label: '春日部つむぎ (Tsumugi) - ノーマル' },
  { id: '10', speakerName: '波音リツ (Namine Ritsu)', styleName: 'ノーマル', label: '波音リツ (Ritsu) - ノーマル' },
  { id: '9', speakerName: '雨晴はう (Amehare Hau)', styleName: 'ノーマル', label: '雨晴はう (Hau) - ノーマル' },
  { id: '14', speakerName: '冥鳴ひまり (Meimei Himari)', styleName: 'ノーマル', label: '冥鳴ひまり (Himari) - -ノーマル' },
  { id: '16', speakerName: '九州そら (Kyushu Sora)', styleName: 'ノーマル', label: '九州そら (Sora) - ノーマル' },
  { id: '15', speakerName: '九州そら (Kyushu Sora)', styleName: 'あまあま', label: '九州そら (Sora) - あまあま' },
  { id: '18', speakerName: '九州そら (Kyushu Sora)', styleName: 'ツンツン', label: '九州そら (Sora) - ツンツン' },
  { id: '17', speakerName: '九州そら (Kyushu Sora)', styleName: 'セクシー', label: '九州そら (Sora) - セクシー' },
  { id: '20', speakerName: 'もち子さん (Mochiko-san)', styleName: 'ノーマル', label: 'もち子さん (Mochiko) - ノーマル' },
  { id: '21', speakerName: '剣崎雌雄 (Kenzaki Shiu)', styleName: 'ノーマル', label: '剣崎雌雄 (Shiu) - ノーマル' },
]

const FALLBACK_KOKORO_SPEAKERS: VoiceOption[] = [
  { id: 'af_bella', speakerName: 'Bella', styleName: 'English (US) Female', label: 'Bella [English (US)] - Female' },
  { id: 'af_sarah', speakerName: 'Sarah', styleName: 'English (US) Female', label: 'Sarah [English (US)] - Female' },
  { id: 'am_adam', speakerName: 'Adam', styleName: 'English (US) Male', label: 'Adam [English (US)] - Male' },
  { id: 'am_michael', speakerName: 'Michael', styleName: 'English (US) Male', label: 'Michael [English (US)] - Male' },
  { id: 'bf_emma', speakerName: 'Emma', styleName: 'English (UK) Female', label: 'Emma [English (UK)] - Female' },
  { id: 'bm_george', speakerName: 'George', styleName: 'English (UK) Male', label: 'George [English (UK)] - Male' },
  { id: 'zf_xiaobei', speakerName: 'Xiaobei', styleName: 'Mandarin Chinese Female', label: 'Xiaobei [Mandarin Chinese] - Female' },
  { id: 'zm_yunjian', speakerName: 'Yunjian', styleName: 'Mandarin Chinese Male', label: 'Yunjian [Mandarin Chinese] - Male' },
  { id: 'ef_dora', speakerName: 'Dora', styleName: 'Spanish Female', label: 'Dora [Spanish] - Female' },
  { id: 'ff_siwis', speakerName: 'Siwis', styleName: 'French Female', label: 'Siwis [French] - Female' },
  { id: 'if_sara', speakerName: 'Sara', styleName: 'Italian Female', label: 'Sara [Italian] - Female' },
  { id: 'pf_dora', speakerName: 'Dora', styleName: 'Portuguese Female', label: 'Dora [Portuguese] - Female' },
  { id: 'hf_alpha', speakerName: 'Alpha', styleName: 'Hindi Female', label: 'Alpha [Hindi] - Female' },
]

function resolveLocaleFromVoiceId(voiceId: string): string {
  if (!voiceId) return 'en-US'
  const prefix = voiceId[0].toLowerCase()
  switch (prefix) {
    case 'a': return 'en-US'
    case 'b': return 'en-GB'
    case 'z': return 'zh-CN'
    case 'e': return 'es-ES'
    case 'f': return 'fr-FR'
    case 'h': return 'hi-IN'
    case 'i': return 'it-IT'
    case 'p': return 'pt-BR'
    default: return 'en-US'
  }
}

function formatVoiceOption(v: Partial<VoiceDescriptor> & { id?: string; label?: string }): VoiceOption {
  const id = String(v.voice_id || v.id || '')
  const speakerName = (v.speaker_name || '').trim()
  const styleName = (v.style_name || '').trim()
  const rawName = (v.name || v.label || '').trim()

  if (speakerName && styleName) {
    return {
      id,
      speakerName,
      styleName,
      label: `${speakerName} - ${styleName}`,
    }
  }

  if (speakerName && rawName) {
    const cleanRaw = rawName.replace(speakerName, '').replace(/^[-_\s()（）]+|[-_\s()（）]+$/g, '').trim()
    return {
      id,
      speakerName,
      styleName: cleanRaw || 'ノーマル',
      label: cleanRaw ? `${speakerName} - ${cleanRaw}` : speakerName,
    }
  }

  if (rawName) {
    const match = rawName.match(/^([^(（]+)\s*[（(]([^)）]+)[)）]$/)
    if (match) {
      return {
        id,
        speakerName: match[1].trim(),
        styleName: match[2].trim(),
        label: `${match[1].trim()} - ${match[2].trim()}`,
      }
    }
    return {
      id,
      speakerName: 'VOICEVOX',
      styleName: rawName,
      label: rawName,
    }
  }

  return {
    id,
    speakerName: 'VOICEVOX',
    styleName: `Style #${id}`,
    label: `VOICEVOX #${id}`,
  }
}

function autoSelectSourceField(fields: string[], currentSource?: string, noteTypeName?: string): string {
  if (currentSource && fields.includes(currentSource)) return currentSource
  const stored = loadStoredLocalAudioSettings()
  if (noteTypeName && stored.fieldMappingByNoteType?.[noteTypeName]?.sourceField) {
    const mapped = stored.fieldMappingByNoteType[noteTypeName].sourceField
    if (mapped && fields.includes(mapped)) return mapped
  }
  if (stored.sourceField && fields.includes(stored.sourceField)) return stored.sourceField
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
  for (const p of sourcePriority) {
    const match = fields.find((f) => f.toLowerCase() === p.toLowerCase())
    if (match) return match
  }
  return fields[0] || ''
}

function autoSelectDestinationField(fields: string[], currentDest?: string, noteTypeName?: string): string {
  if (currentDest && fields.includes(currentDest)) return currentDest
  const stored = loadStoredLocalAudioSettings()
  if (noteTypeName && stored.fieldMappingByNoteType?.[noteTypeName]?.destinationField) {
    const mapped = stored.fieldMappingByNoteType[noteTypeName].destinationField
    if (mapped && fields.includes(mapped)) return mapped
  }
  if (stored.destinationField && fields.includes(stored.destinationField)) return stored.destinationField
  const destPriority = [
    'Audio', 'audio',
    'AudioReading', 'audioreading',
    'Sound', 'sound',
    'AudioWord', 'audioword',
    'Pronunciation', 'pronunciation',
    'Voice', 'voice',
  ]
  for (const p of destPriority) {
    const match = fields.find((f) => f.toLowerCase() === p.toLowerCase())
    if (match) return match
  }
  return fields[0] || ''
}

export function useLocalAudioEngine(options: {
  isOpen: boolean
  selectedCardIds: string[]
  activeCardId?: string | null
  deckId?: number | null
  deckName?: string
  availableFieldNames?: string[]
  availableAudioFieldNames?: string[]
  noteTypeName?: string
  engineId?: 'voicevox' | 'kokoro'
  defaultVoiceId?: string
  onSuccess?: () => void
}) {
  const {
    isOpen,
    selectedCardIds,
    activeCardId,
    deckId,
    availableFieldNames = ['Reading', 'Word', 'Meaning'],
    availableAudioFieldNames = ['Audio'],
    engineId = 'voicevox',
    defaultVoiceId,
    onSuccess,
  } = options

  const isKokoro = engineId === 'kokoro'

  const [deckScanResult, setDeckScanResult] = useState<DeckScanResponse | null>(null)
  const [isScanningDeck, setIsScanningDeck] = useState<boolean>(false)
  const [discoveredNoteTypeName, setDiscoveredNoteTypeName] = useState<string | undefined>(options.noteTypeName)
  const activeNoteTypeName = options.noteTypeName || discoveredNoteTypeName

  useEffect(() => {
    if (isOpen && selectedCardIds.length === 0 && deckId) {
      setIsScanningDeck(true)
      scanDeckAudio(deckId)
        .then((res) => {
          setDeckScanResult(res)
          if (res.note_types?.[0]?.name) {
            setDiscoveredNoteTypeName(res.note_types[0].name)
          }
          const allFields = res.note_types?.[0]?.fields || []
          if (allFields.length > 0) {
            const sourceNames = allFields
              .filter((f) => !['audio', 'sound'].includes(String(f.field_type || '').toLowerCase()))
              .map((f) => f.name)
            const audioNames = allFields
              .filter((f) => ['audio', 'sound'].includes(String(f.field_type || '').toLowerCase()))
              .map((f) => f.name)
            if (sourceNames.length > 0) setDynamicFields(sourceNames)
            if (audioNames.length > 0) setDynamicAudioFields(audioNames)
          }
        })
        .catch(() => {
          setDeckScanResult(null)
        })
        .finally(() => {
          setIsScanningDeck(false)
        })
    } else {
      setDeckScanResult(null)
    }
  }, [isOpen, selectedCardIds.length, deckId])

  const deckCardIds = useMemo(() => {
    if (!deckScanResult?.notes) return []
    return deckScanResult.notes.map((n) => n.card_id).filter(Boolean)
  }, [deckScanResult])

  const hasMixedNoteTypes = useMemo(() => {
    if (selectedCardIds.length > 0) return false
    if (!deckScanResult?.note_types) return false
    return deckScanResult.note_types.length > 1
  }, [selectedCardIds.length, deckScanResult])

  const targetCardIds = useMemo(() => {
    if (selectedCardIds.length > 0) return selectedCardIds
    if (deckId && deckCardIds.length > 0) return deckCardIds
    return activeCardId ? [activeCardId] : []
  }, [selectedCardIds, deckId, deckCardIds, activeCardId])

  // Service & Pairing State
  const [serviceStatus, setServiceStatus] = useState<'checking' | 'offline' | 'online'>('checking')
  const [pairingChallengeId, setPairingChallengeId] = useState<string | null>(null)
  const [isPairingApproved, setIsPairingApproved] = useState<boolean>(false)

  // Voice Selection State
  const initialLocalSettings = loadStoredLocalAudioSettings()

  const resolveInitialVoiceId = useCallback((engine: 'voicevox' | 'kokoro', defaultId?: string) => {
    const stored = loadStoredLocalAudioSettings()
    if (engine === 'kokoro') {
      const targetLang = defaultId ? getLanguageGroupFromVoiceId(defaultId) : undefined
      if (targetLang && stored.lastVoiceIdKokoroByLang?.[targetLang]) {
        return stored.lastVoiceIdKokoroByLang[targetLang]
      }
      if (defaultId && stored.lastVoiceIdKokoro) {
        const targetPrefix = defaultId[0].toLowerCase()
        const storedPrefix = stored.lastVoiceIdKokoro[0].toLowerCase()
        const isTargetEn = targetPrefix === 'a' || targetPrefix === 'b'
        const isStoredEn = storedPrefix === 'a' || storedPrefix === 'b'
        if ((isTargetEn && isStoredEn) || targetPrefix === storedPrefix) {
          return stored.lastVoiceIdKokoro
        }
      }
      return defaultId || stored.lastVoiceIdKokoro || 'af_bella'
    }
    // For VoiceVox, ALWAYS preserve user's last chosen VoiceVox voice if available!
    return stored.lastVoiceIdVoicevox || defaultId || '3'
  }, [])

  const [voices, setVoices] = useState<VoiceDescriptor[]>([])
  const [selectedVoiceId, setSelectedVoiceIdState] = useState<string>(() => {
    return resolveInitialVoiceId(engineId, defaultVoiceId)
  })

  const setSelectedVoiceId = useCallback((voiceId: string) => {
    setSelectedVoiceIdState(voiceId)
    if (isKokoro) {
      const lang = getLanguageGroupFromVoiceId(voiceId)
      const currentByLang = loadStoredLocalAudioSettings().lastVoiceIdKokoroByLang || {}
      saveStoredLocalAudioSettings({
        lastVoiceIdKokoro: voiceId,
        lastVoiceIdKokoroByLang: {
          ...currentByLang,
          [lang]: voiceId,
        },
      })
    } else {
      saveStoredLocalAudioSettings({ lastVoiceIdVoicevox: voiceId })
    }
  }, [isKokoro])

  useEffect(() => {
    setSelectedVoiceIdState(resolveInitialVoiceId(engineId, defaultVoiceId))
    setVoices([])
  }, [engineId, defaultVoiceId, resolveInitialVoiceId])

  // Dynamic Fields Resolution State
  const [dynamicFields, setDynamicFields] = useState<string[]>(availableFieldNames)
  const [dynamicAudioFields, setDynamicAudioFields] = useState<string[]>(
    availableAudioFieldNames,
  )

  useEffect(() => {
    setDynamicFields(availableFieldNames)
  }, [availableFieldNames])

  useEffect(() => {
    setDynamicAudioFields(availableAudioFieldNames)
  }, [availableAudioFieldNames])

  // Fetch card details dynamically if fields are missing
  useEffect(() => {
    if (isOpen && targetCardIds.length > 0) {
      const cardId = targetCardIds[0]
      apiRequest<{
        card: { word: string }
        fields?: Array<{ name: string; field_type?: string }>
        note?: { note_type_name?: string; field_values?: Record<string, string> }
      }>(`/api/browse/cards/${encodeURIComponent(cardId)}`)
        .then((res) => {
          if (res.note?.note_type_name) {
            setDiscoveredNoteTypeName(res.note.note_type_name)
          }
          if (res.fields && res.fields.length > 0) {
            const sourceNames = res.fields
              .filter((field) => !['image', 'audio', 'diagram'].includes(String(field.field_type || '').toLowerCase()))
              .map((field) => field.name)
              .filter(Boolean)
            const audioNames = res.fields
              .filter((field) => String(field.field_type || '').toLowerCase() === 'audio')
              .map((field) => field.name)
              .filter(Boolean)
            setDynamicFields(sourceNames)
            setDynamicAudioFields(audioNames)
          } else if (res.note?.field_values) {
            const names = Object.keys(res.note.field_values)
            const guessedAudioNames = names.filter((name) => /audio|sound/i.test(name))
            setDynamicFields(names.filter((name) => !guessedAudioNames.includes(name)))
            setDynamicAudioFields(guessedAudioNames)
          }
        })
        .catch(() => {})
    }
  }, [isOpen, targetCardIds])

  // Source & Destination Fields Sync
  const [sourceField, setSourceFieldState] = useState<string>(() => {
    return initialLocalSettings.sourceField || 'Reading'
  })
  const setSourceField = useCallback((field: string) => {
    setSourceFieldState(field)
    const updates: Partial<LocalAudioSettings> = { sourceField: field }
    if (activeNoteTypeName) {
      const currentMapping = loadStoredLocalAudioSettings().fieldMappingByNoteType || {}
      updates.fieldMappingByNoteType = {
        ...currentMapping,
        [activeNoteTypeName]: {
          ...(currentMapping[activeNoteTypeName] || {}),
          sourceField: field,
        },
      }
    }
    saveStoredLocalAudioSettings(updates)
  }, [activeNoteTypeName])

  const [destinationField, setDestinationFieldState] = useState<string>(() => {
    return initialLocalSettings.destinationField || 'Audio'
  })
  const setDestinationField = useCallback((field: string) => {
    setDestinationFieldState(field)
    const updates: Partial<LocalAudioSettings> = { destinationField: field }
    if (activeNoteTypeName) {
      const currentMapping = loadStoredLocalAudioSettings().fieldMappingByNoteType || {}
      updates.fieldMappingByNoteType = {
        ...currentMapping,
        [activeNoteTypeName]: {
          ...(currentMapping[activeNoteTypeName] || {}),
          destinationField: field,
        },
      }
    }
    saveStoredLocalAudioSettings(updates)
  }, [activeNoteTypeName])

  useEffect(() => {
    if (isOpen && dynamicFields.length > 0) {
      setSourceFieldState((prev) => autoSelectSourceField(dynamicFields, prev, activeNoteTypeName))
    }
  }, [isOpen, dynamicFields, activeNoteTypeName])

  useEffect(() => {
    if (isOpen && dynamicAudioFields.length > 0) {
      setDestinationFieldState((prev) => autoSelectDestinationField(dynamicAudioFields, prev, activeNoteTypeName))
    }
  }, [isOpen, dynamicAudioFields, activeNoteTypeName])

  // Advanced Sliders State - Isolated per engine
  const [volumeScale, setVolumeScaleState] = useState<number>(() => {
    return isKokoro
      ? (initialLocalSettings.volumeScaleKokoro ?? initialLocalSettings.volumeScale)
      : (initialLocalSettings.volumeScaleVoicevox ?? initialLocalSettings.volumeScale)
  })
  const setVolumeScale = (val: number | ((prev: number) => number)) => {
    setVolumeScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      if (isKokoro) {
        saveStoredLocalAudioSettings({ volumeScale: next, volumeScaleKokoro: next })
      } else {
        saveStoredLocalAudioSettings({ volumeScale: next, volumeScaleVoicevox: next })
      }
      return next
    })
  }

  const [pitch, setPitchState] = useState<number>(() => {
    return isKokoro
      ? (initialLocalSettings.pitchKokoro ?? initialLocalSettings.pitch)
      : (initialLocalSettings.pitchVoicevox ?? initialLocalSettings.pitch)
  })
  const setPitch = (val: number | ((prev: number) => number)) => {
    setPitchState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      if (isKokoro) {
        saveStoredLocalAudioSettings({ pitch: next, pitchKokoro: next })
      } else {
        saveStoredLocalAudioSettings({ pitch: next, pitchVoicevox: next })
      }
      return next
    })
  }

  const [speed, setSpeedState] = useState<number>(() => {
    return isKokoro
      ? (initialLocalSettings.speedKokoro ?? initialLocalSettings.speed)
      : (initialLocalSettings.speedVoicevox ?? initialLocalSettings.speed)
  })
  const setSpeed = (val: number | ((prev: number) => number)) => {
    setSpeedState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      if (isKokoro) {
        saveStoredLocalAudioSettings({ speed: next, speedKokoro: next })
      } else {
        saveStoredLocalAudioSettings({ speed: next, speedVoicevox: next })
      }
      return next
    })
  }

  const [intonationScale, setIntonationScaleState] = useState<number>(() => {
    return isKokoro
      ? (initialLocalSettings.intonationScaleKokoro ?? initialLocalSettings.intonationScale)
      : (initialLocalSettings.intonationScaleVoicevox ?? initialLocalSettings.intonationScale)
  })
  const setIntonationScale = (val: number | ((prev: number) => number)) => {
    setIntonationScaleState((prev) => {
      const next = typeof val === 'function' ? val(prev) : val
      if (isKokoro) {
        saveStoredLocalAudioSettings({ intonationScale: next, intonationScaleKokoro: next })
      } else {
        saveStoredLocalAudioSettings({ intonationScale: next, intonationScaleVoicevox: next })
      }
      return next
    })
  }

  useEffect(() => {
    const s = loadStoredLocalAudioSettings()
    if (isKokoro) {
      setSpeedState(s.speedKokoro ?? s.speed ?? 1.0)
      setPitchState(s.pitchKokoro ?? s.pitch ?? 0.0)
      setVolumeScaleState(s.volumeScaleKokoro ?? s.volumeScale ?? 1.0)
      setIntonationScaleState(s.intonationScaleKokoro ?? s.intonationScale ?? 1.0)
    } else {
      setSpeedState(s.speedVoicevox ?? s.speed ?? 1.0)
      setPitchState(s.pitchVoicevox ?? s.pitch ?? 0.0)
      setVolumeScaleState(s.volumeScaleVoicevox ?? s.volumeScale ?? 1.0)
      setIntonationScaleState(s.intonationScaleVoicevox ?? s.intonationScale ?? 1.0)
    }
  }, [isKokoro, isOpen])

  // Audio Preview State
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  // Batch Execution Queue State
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [progressPercent, setProgressPercent] = useState<number>(0)
  const [items, setItems] = useState<BatchItem[]>([])

  // Engine Install & Action State
  const [engineOffline, setEngineOffline] = useState<boolean>(false)
  const [engineActionState, setEngineActionState] = useState<'idle' | 'installing' | 'launching'>('idle')

  // Backend Voices Fallback Fetch
  useEffect(() => {
    if (isOpen && voices.length === 0) {
      apiRequest<{ items: Array<{ id: string; label: string; speaker_name: string; style_name: string }> }>(
        '/api/tts/providers/voicevox/voices',
        { method: 'POST', body: JSON.stringify({}) },
      )
        .then((res) => {
          if (res?.items && res.items.length > 0) {
            const converted: VoiceDescriptor[] = res.items.map((item) => ({
              voice_id: String(item.id),
              name: item.label,
              speaker_name: item.speaker_name,
              style_name: item.style_name,
              locale: 'ja-JP',
              commercial_safe: true,
            }))
            setVoices((curr) => (curr.length === 0 ? converted : curr))
          }
        })
        .catch(() => {})
    }
  }, [isOpen, voices.length])

  // Formatted Voice Options List
  const voiceOptions = useMemo<VoiceOption[]>(() => {
    let rawOptions: VoiceOption[] = []
    if (voices.length > 0) {
      rawOptions = voices.map((v) => formatVoiceOption(v))
    } else {
      rawOptions = isKokoro ? FALLBACK_KOKORO_SPEAKERS : FALLBACK_VOICEVOX_SPEAKERS
    }

    if (isKokoro && defaultVoiceId) {
      const targetPrefix = defaultVoiceId[0].toLowerCase()
      rawOptions = rawOptions.filter((opt) => {
        const prefix = opt.id ? opt.id[0].toLowerCase() : 'a'
        if (targetPrefix === 'a' || targetPrefix === 'b') {
          return prefix === 'a' || prefix === 'b'
        }
        return prefix === targetPrefix
      })
    }

    return rawOptions
  }, [voices, isKokoro, defaultVoiceId])

  const groupedVoiceOptions = useMemo<Record<string, VoiceOption[]>>(() => {
    const groups: Record<string, VoiceOption[]> = {}
    for (const opt of voiceOptions) {
      let key = opt.speakerName || 'VOICEVOX'
      if (isKokoro) {
        const prefix = opt.id ? opt.id[0].toLowerCase() : 'a'
        switch (prefix) {
          case 'a': key = '🇺🇸 English (US)'; break
          case 'b': key = '🇬🇧 English (UK)'; break
          case 'z': key = '🇨🇳 Mandarin Chinese (中文)'; break
          case 'e': key = '🇪🇸 Spanish (Español)'; break
          case 'f': key = '🇫🇷 French (Français)'; break
          case 'h': key = '🇮🇳 Hindi (हिन्दी)'; break
          case 'i': key = '🇮🇹 Italian (Italiano)'; break
          case 'p': key = '🇧🇷 Portuguese (Português)'; break
          default: key = '🌐 Other Languages'
        }
      }
      if (!groups[key]) groups[key] = []
      groups[key].push(opt)
    }
    return groups
  }, [voiceOptions, isKokoro])

  useEffect(() => {
    if (voiceOptions.length > 0 && !voiceOptions.some((v) => v.id === selectedVoiceId)) {
      setSelectedVoiceId(voiceOptions[0].id)
    }
  }, [voiceOptions, selectedVoiceId, setSelectedVoiceId])

  const handleInstallEngine = async () => {
    setEngineActionState('installing')
    const targetEngine = engineId || 'voicevox'
    const engineLabel = isKokoro ? 'Kokoro-82M' : 'VOICEVOX'
    try {
      toast.info(`Đang gửi yêu cầu tải & cài đặt ${engineLabel} Engine... Vui lòng chờ trong giây lát.`)
      const res = await flamaAudioClient.installEngine(targetEngine)
      toast.success(res.message || `Đã gửi lệnh cài đặt ${engineLabel} thành công. Đang chờ Engine khởi động...`)

      let count = 0
      const timer = setInterval(async () => {
        count++
        try {
          const voiceList = await flamaAudioClient.getVoices(targetEngine)
          if (voiceList.length > 0) {
            clearInterval(timer)
            setVoices(voiceList)
            setEngineOffline(false)
            setEngineActionState('idle')
            toast.success(`${engineLabel} Engine đã sẵn sàng!`)
          }
        } catch {
          if (count >= 15) {
            clearInterval(timer)
            setEngineActionState('idle')
            toast.error('Quá thời gian chờ Engine khởi động. Vui lòng kiểm tra lại ứng dụng Desktop.')
          }
        }
      }, 2000)
    } catch (err) {
      setEngineActionState('idle')
      toast.error(err instanceof Error ? err.message : 'Tải Engine thất bại.')
    }
  }

  const handleLaunchEngine = async () => {
    setEngineActionState('launching')
    const targetEngine = engineId || 'voicevox'
    const engineLabel = isKokoro ? 'Kokoro-82M' : 'VOICEVOX'
    try {
      toast.info(`Đang kích hoạt ${engineLabel} Engine local...`)
      const res = await flamaAudioClient.launchEngine(targetEngine)
      toast.success(res.message || 'Đã phát lệnh mở Engine.')

      let count = 0
      const timer = setInterval(async () => {
        count++
        try {
          const voiceList = await flamaAudioClient.getVoices(targetEngine)
          if (voiceList.length > 0) {
            clearInterval(timer)
            setVoices(voiceList)
            setEngineOffline(false)
            setEngineActionState('idle')
            toast.success(`${engineLabel} Engine đã kết nối!`)
          }
        } catch {
          if (count >= 8) {
            clearInterval(timer)
            setEngineActionState('idle')
          }
        }
      }, 1500)
    } catch (err) {
      setEngineActionState('idle')
      toast.error(err instanceof Error ? err.message : 'Khởi chạy Engine thất bại.')
    }
  }

  const handleResetDefaults = () => {
    if (isKokoro) {
      saveStoredLocalAudioSettings({
        volumeScaleKokoro: 1.0,
        pitchKokoro: 0.0,
        speedKokoro: 1.0,
        intonationScaleKokoro: 1.0,
      })
    } else {
      saveStoredLocalAudioSettings({
        volumeScaleVoicevox: 1.0,
        pitchVoicevox: 0.0,
        speedVoicevox: 1.0,
        intonationScaleVoicevox: 1.0,
      })
    }
    setVolumeScaleState(1.0)
    setPitchState(0.0)
    setSpeedState(1.0)
    setIntonationScaleState(1.0)
    toast.info('Đã khôi phục thông số âm thanh mặc định.')
  }

  const handleStartPairing = useCallback(async () => {
    try {
      const challenge = await flamaAudioClient.startPairing(window.location.origin)
      setPairingChallengeId(challenge.pairing_id)

      if (challenge.approved && challenge.token) {
        flamaAudioClient.setToken(challenge.token)
        setIsPairingApproved(true)
        toast.success('Ghép nối với Flama Audio thành công!')
        try {
          const voiceList = await flamaAudioClient.getVoices(engineId)
          if (voiceList.length > 0) setVoices(voiceList)
        } catch {}
        return
      }

      let attempts = 0
      const interval = setInterval(async () => {
        attempts++
        if (attempts > 40) {
          clearInterval(interval)
          setPairingChallengeId(null)
          return
        }

        try {
          const status = await flamaAudioClient.getPairingStatus(challenge.pairing_id)
          if (status.approved && status.token) {
            clearInterval(interval)
            flamaAudioClient.setToken(status.token)
            setIsPairingApproved(true)
            setPairingChallengeId(null)
            toast.success('Đã phê duyệt ghép nối Flama Audio!')
            try {
              const voiceList = await flamaAudioClient.getVoices(engineId)
              if (voiceList.length > 0) setVoices(voiceList)
            } catch {}
          }
        } catch {}
      }, 1500)
    } catch {
      toast.error('Không thể gửi yêu cầu ghép nối tới local service.')
    }
  }, [engineId])

  const checkHealthAndInit = useCallback(async () => {
    setServiceStatus('checking')
    try {
      await flamaAudioClient.getHealth()
      setServiceStatus('online')

      const token = flamaAudioClient.getToken()
      if (!token) {
        setIsPairingApproved(false)
        handleStartPairing()
        return
      }

      try {
        const voiceList = await flamaAudioClient.getVoices(engineId)
        if (voiceList.length > 0) {
          setVoices(voiceList)
        }
        setIsPairingApproved(true)
      } catch {
        setIsPairingApproved(false)
        handleStartPairing()
      }
    } catch {
      setServiceStatus('offline')
    }
  }, [engineId, handleStartPairing])

  useEffect(() => {
    if (isOpen) {
      checkHealthAndInit()
    }
  }, [isOpen, checkHealthAndInit])

  const handlePreviewAudio = async () => {
    setIsPreviewing(true)
    try {
      let sampleText = isKokoro ? 'Hello, welcome to Flama Audio!' : 'こんにちは'
      if (targetCardIds.length > 0) {
        try {
          const detail = await apiRequest<{
            card: { word: string }
            note: { field_values?: Record<string, string> }
          }>(`/api/browse/cards/${encodeURIComponent(targetCardIds[0])}`)
          const raw = detail.note?.field_values?.[sourceField] || detail.card.word || sampleText
          sampleText = cleanTextForTts(raw, engineId) || sampleText
        } catch {}
      }

      const wavBlob = await flamaAudioClient.synthesize({
        request_id: `preview_${Date.now()}`,
        engine_id: engineId,
        language: isKokoro ? resolveLocaleFromVoiceId(selectedVoiceId) : 'ja-JP',
        voice_id: selectedVoiceId,
        text: sampleText,
        options: { speed, pitch, intonation: intonationScale, volume: volumeScale },
      })

      const audioUrl = URL.createObjectURL(wavBlob)
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause()
      }
      const audio = new Audio(audioUrl)
      audioPlayerRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl)
        setIsPreviewing(false)
      }
      await audio.play()
    } catch (err) {
      setIsPreviewing(false)
      const msg = err instanceof Error ? err.message : 'Nghe thử thất bại.'
      if (msg.includes('50021') || msg.includes('VOICEVOX Engine')) {
        setEngineOffline(true)
      }
      toast.error(msg)
    }
  }

  const handleStartBatch = async () => {
    if (hasMixedNoteTypes) {
      toast.error('Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác.')
      return
    }
    if (targetCardIds.length === 0) {
      toast.error('Vui lòng chọn ít nhất 1 thẻ từ vựng.')
      return
    }
    if (!destinationField) {
      toast.error('Note Type cần có ít nhất một trường kiểu audio.')
      return
    }

    setIsProcessing(true)
    setProgressPercent(0)

    // Step 1: Pre-fetch card details in parallel chunks
    const CHUNK_SIZE = 8
    const batchItems: BatchItem[] = new Array(targetCardIds.length)

    for (let i = 0; i < targetCardIds.length; i += CHUNK_SIZE) {
      const chunk = targetCardIds.slice(i, i + CHUNK_SIZE)
      await Promise.all(
        chunk.map(async (cardId, chunkIdx) => {
          const globalIdx = i + chunkIdx
          try {
            const detail = await apiRequest<{
              card: { word: string }
              note: { id: string; field_values?: Record<string, string> }
              can_upload_media?: boolean
            }>(`/api/browse/cards/${encodeURIComponent(cardId)}`)

            const noteValues = detail.note.field_values || {}
            const rawText =
              noteValues[sourceField] ||
              noteValues['Reading'] ||
              noteValues['reading'] ||
              detail.card.word ||
              ''
            const wordText = cleanTextForTts(rawText, engineId)

            if (detail.can_upload_media === false) {
              batchItems[globalIdx] = {
                cardId,
                noteId: detail.note.id,
                word: detail.card.word,
                sourceText: wordText,
                status: 'skipped',
                error: 'Bộ thẻ Clone không hỗ trợ tạo media trực tiếp',
              }
            } else {
              batchItems[globalIdx] = {
                cardId,
                noteId: detail.note.id,
                word: detail.card.word,
                sourceText: wordText,
                status: 'pending',
              }
            }
          } catch {
            batchItems[globalIdx] = {
              cardId,
              noteId: '',
              word: cardId,
              sourceText: '',
              status: 'failed',
              error: 'Không thể tải chi tiết thẻ',
            }
          }
        })
      )
    }

    setItems([...batchItems])

    const total = batchItems.length
    const itemsToProcess = batchItems
      .map((item, index) => ({ item, index }))
      .filter(({ item }) => item.status === 'pending')

    let completedCount = total - itemsToProcess.length
    setProgressPercent(total > 0 ? Math.round((completedCount / total) * 100) : 100)

    // Step 2: Concurrency Worker Pool for TTS + Batch Upload
    const TTS_CONCURRENCY = 3
    const UPLOAD_BATCH_SIZE = 15

    type SynthesizedEntry = {
      index: number
      item: BatchItem
      blob: Blob
    }

    const uploadBuffer: SynthesizedEntry[] = []

    const flushUploadBuffer = async () => {
      if (uploadBuffer.length === 0) return
      const currentBatch = [...uploadBuffer]
      uploadBuffer.length = 0

      // Mark status as uploading
      currentBatch.forEach(({ index }) => {
        batchItems[index].status = 'uploading'
      })
      setItems([...batchItems])

      try {
        const batchPayload: BatchMediaItemInput[] = currentBatch.map(({ index, item, blob }) => ({
          itemId: String(index),
          noteId: item.noteId,
          fieldName: destinationField,
          blob,
          filename: `${engineId}_${item.cardId}.wav`,
        }))

        const res = await uploadNoteMediaBatch(batchPayload)
        const resultMap = new Map(res.items.map((it) => [it.item_id, it]))

        currentBatch.forEach(({ index, item }) => {
          const result = resultMap.get(String(index))
          if (result && result.status === 'success') {
            batchItems[index].status = 'done'
            if (result.url) {
              updateCardFieldValuesInSessions(item.cardId, { [destinationField]: result.url })
            }
          } else {
            batchItems[index].status = 'failed'
            batchItems[index].error = result?.message || result?.error || 'Tải lên thất bại'
          }
          completedCount++
        })
      } catch {
        // Fallback to single upload per item if batch upload endpoint fails
        for (const { index, item, blob } of currentBatch) {
          try {
            const res = await uploadNoteMediaBlob(
              item.noteId,
              destinationField,
              blob,
              `${engineId}_${item.cardId}.wav`,
            )
            batchItems[index].status = 'done'
            if (res.url) {
              updateCardFieldValuesInSessions(item.cardId, { [destinationField]: res.url })
            }
          } catch (err) {
            batchItems[index].status = 'failed'
            batchItems[index].error = err instanceof Error ? err.message : 'Tạo audio thất bại'
          }
          completedCount++
        }
      }

      setItems([...batchItems])
      setProgressPercent(Math.round((completedCount / total) * 100))
    }

    let currentIndex = 0

    const ttsWorker = async () => {
      while (currentIndex < itemsToProcess.length) {
        const nextIdx = currentIndex++
        const { item, index } = itemsToProcess[nextIdx]

        if (!item.sourceText.trim()) {
          batchItems[index].status = 'failed'
          batchItems[index].error = `Trường '${sourceField}' rỗng`
          completedCount++
          setItems([...batchItems])
          setProgressPercent(Math.round((completedCount / total) * 100))
          continue
        }

        batchItems[index].status = 'synthesizing'
        setItems([...batchItems])

        try {
          const wavBlob = await flamaAudioClient.synthesize({
            request_id: `req_${Date.now()}_${index}`,
            engine_id: engineId,
            language: isKokoro ? resolveLocaleFromVoiceId(selectedVoiceId) : 'ja-JP',
            voice_id: selectedVoiceId,
            text: item.sourceText,
            options: { speed, pitch, intonation: intonationScale, volume: volumeScale },
          })

          uploadBuffer.push({ index, item, blob: wavBlob })
          if (uploadBuffer.length >= UPLOAD_BATCH_SIZE) {
            await flushUploadBuffer()
          }
        } catch (err) {
          batchItems[index].status = 'failed'
          batchItems[index].error = err instanceof Error ? err.message : 'Tạo audio thất bại'
          completedCount++
          setItems([...batchItems])
          setProgressPercent(Math.round((completedCount / total) * 100))
        }
      }
    }

    if (itemsToProcess.length > 0) {
      const activeWorkers = Math.min(TTS_CONCURRENCY, itemsToProcess.length)
      await Promise.all(Array.from({ length: activeWorkers }, () => ttsWorker()))
      await flushUploadBuffer()
    }

    setIsProcessing(false)
    toast.success(`Đã hoàn tất quá trình tạo audio ${isKokoro ? 'Kokoro Local' : 'VOICEVOX'}!`)
    if (onSuccess) onSuccess()
  }

  return {
    isKokoro,
    targetCardIds,
    serviceStatus,
    pairingChallengeId,
    isPairingApproved,
    selectedVoiceId,
    setSelectedVoiceId,
    dynamicFields,
    dynamicAudioFields,
    sourceField,
    setSourceField,
    destinationField,
    setDestinationField,
    volumeScale,
    setVolumeScale,
    pitch,
    setPitch,
    speed,
    setSpeed,
    intonationScale,
    setIntonationScale,
    isPreviewing,
    isProcessing,
    progressPercent,
    items,
    deckScanResult,
    isScanningDeck,
    hasMixedNoteTypes,
    engineOffline,
    engineActionState,
    voiceOptions,
    groupedVoiceOptions,
    handleInstallEngine,
    handleLaunchEngine,
    handleResetDefaults,
    handlePreviewAudio,
    handleStartBatch,
    checkHealthAndInit,
    handleStartPairing,
  }
}

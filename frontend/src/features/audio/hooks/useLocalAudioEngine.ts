import { useEffect, useMemo, useRef, useState, useCallback } from 'react'
import { toast } from 'sonner'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { apiRequest } from '@/shared/api/client'
import { uploadNoteMediaBlob } from '@/shared/api/noteMedia'
import type { VoiceDescriptor } from '../types'

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

function autoSelectSourceField(fields: string[], currentSource?: string): string {
  if (currentSource && fields.includes(currentSource)) return currentSource
  const sourcePriority = ['Reading', 'reading', 'Word', 'word', 'Expression', 'expression', 'Kanji', 'kanji']
  for (const p of sourcePriority) {
    const match = fields.find((f) => f.toLowerCase() === p.toLowerCase())
    if (match) return match
  }
  return fields[0] || 'Word'
}

function autoSelectDestinationField(fields: string[], currentDest?: string): string {
  if (currentDest && fields.includes(currentDest)) return currentDest
  const destPriority = ['Audio', 'audio', 'AudioReading', 'audioreading', 'Sound', 'sound', 'AudioWord', 'audioword']
  for (const p of destPriority) {
    const match = fields.find((f) => f.toLowerCase() === p.toLowerCase())
    if (match) return match
  }
  return fields[fields.length - 1] || 'Audio'
}

function cleanTextForVoiceVox(rawText: string): string {
  if (!rawText) return ''
  let text = rawText

  // Strip HTML tags
  text = text.replace(/<[^>]*>/g, ' ')

  // Replace Japanese furigana brackets: 漢字[かんじ] -> かんじ or 漢字(かんじ) -> かんじ
  text = text.replace(/[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]+\s*\[([^\]]+)\]/g, '$1')
  text = text.replace(/[\u4e00-\u9faf\u3040-\u309f\u30a0-\u30ff]+\s*\(([^)]+)\)/g, '$1')

  // Strip [sound:...] media tags
  text = text.replace(/\[sound:[^\]]+\]/gi, '')

  // Decode common HTML entities
  text = text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')

  return text.replace(/\s+/g, ' ').trim()
}

export function useLocalAudioEngine(options: {
  isOpen: boolean
  selectedCardIds: string[]
  activeCardId?: string | null
  availableFieldNames?: string[]
  engineId?: 'voicevox' | 'kokoro'
  defaultVoiceId?: string
  onSuccess?: () => void
}) {
  const {
    isOpen,
    selectedCardIds,
    activeCardId,
    availableFieldNames = ['Reading', 'Word', 'Meaning', 'Audio'],
    engineId = 'voicevox',
    defaultVoiceId,
    onSuccess,
  } = options

  const isKokoro = engineId === 'kokoro'

  const targetCardIds = useMemo(() => {
    return selectedCardIds.length > 0 ? selectedCardIds : activeCardId ? [activeCardId] : []
  }, [selectedCardIds, activeCardId])

  // Service & Pairing State
  const [serviceStatus, setServiceStatus] = useState<'checking' | 'offline' | 'online'>('checking')
  const [pairingChallengeId, setPairingChallengeId] = useState<string | null>(null)
  const [isPairingApproved, setIsPairingApproved] = useState<boolean>(false)

  // Voice Selection State
  const [voices, setVoices] = useState<VoiceDescriptor[]>([])
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>(defaultVoiceId || (isKokoro ? 'af_bella' : '3'))

  useEffect(() => {
    setSelectedVoiceId(defaultVoiceId || (isKokoro ? 'af_bella' : '3'))
    setVoices([])
  }, [engineId, isKokoro, defaultVoiceId])

  // Dynamic Fields Resolution State
  const [dynamicFields, setDynamicFields] = useState<string[]>(availableFieldNames)

  useEffect(() => {
    if (availableFieldNames && availableFieldNames.length > 0) {
      setDynamicFields(availableFieldNames)
    }
  }, [availableFieldNames])

  // Fetch card details dynamically if fields are missing
  useEffect(() => {
    if (isOpen && targetCardIds.length > 0) {
      const cardId = targetCardIds[0]
      apiRequest<{
        card: { word: string }
        fields?: Array<{ name: string }>
        note?: { field_values?: Record<string, string> }
      }>(`/api/browse/cards/${encodeURIComponent(cardId)}`)
        .then((res) => {
          if (res.fields && res.fields.length > 0) {
            const names = res.fields.map((f) => f.name).filter(Boolean)
            if (names.length > 0) setDynamicFields(names)
          } else if (res.note?.field_values) {
            const names = Object.keys(res.note.field_values)
            if (names.length > 0) setDynamicFields(names)
          }
        })
        .catch(() => {})
    }
  }, [isOpen, targetCardIds])

  // Source & Destination Fields Sync
  const [sourceField, setSourceField] = useState<string>('Reading')
  const [destinationField, setDestinationField] = useState<string>('Audio')

  useEffect(() => {
    if (isOpen && dynamicFields.length > 0) {
      setSourceField((prev) => autoSelectSourceField(dynamicFields, prev))
      setDestinationField((prev) => autoSelectDestinationField(dynamicFields, prev))
    }
  }, [isOpen, dynamicFields])

  // Advanced Sliders State
  const [volumeScale, setVolumeScale] = useState<number>(1.0)
  const [pitch, setPitch] = useState<number>(0.0)
  const [speed, setSpeed] = useState<number>(1.0)
  const [intonationScale, setIntonationScale] = useState<number>(1.0)

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
  }, [voiceOptions, selectedVoiceId])

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
    setVolumeScale(1.0)
    setPitch(0.0)
    setSpeed(1.0)
    setIntonationScale(1.0)
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
          sampleText = cleanTextForVoiceVox(raw) || sampleText
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
    if (targetCardIds.length === 0) {
      toast.error('Vui lòng chọn ít nhất 1 thẻ từ vựng.')
      return
    }

    setIsProcessing(true)
    setProgressPercent(0)

    const batchItems: BatchItem[] = []
    for (const cardId of targetCardIds) {
      try {
        const detail = await apiRequest<{
          card: { word: string }
          note: { id: string; field_values?: Record<string, string> }
          can_upload_media?: boolean
        }>(`/api/browse/cards/${encodeURIComponent(cardId)}`)

        const noteValues = detail.note.field_values || {}
        const rawText = noteValues[sourceField] || noteValues['Reading'] || noteValues['reading'] || detail.card.word || ''
        const wordText = cleanTextForVoiceVox(rawText)

        if (detail.can_upload_media === false) {
          batchItems.push({
            cardId,
            noteId: detail.note.id,
            word: detail.card.word,
            sourceText: wordText,
            status: 'skipped',
            error: 'Bộ thẻ Clone không hỗ trợ tạo media trực tiếp',
          })
        } else {
          batchItems.push({
            cardId,
            noteId: detail.note.id,
            word: detail.card.word,
            sourceText: wordText,
            status: 'pending',
          })
        }
      } catch {
        batchItems.push({
          cardId,
          noteId: '',
          word: cardId,
          sourceText: '',
          status: 'failed',
          error: 'Không thể tải chi tiết thẻ',
        })
      }
    }

    setItems([...batchItems])

    const total = batchItems.length
    let completedCount = 0

    for (let i = 0; i < batchItems.length; i++) {
      const item = batchItems[i]
      if (item.status === 'skipped' || item.status === 'failed') {
        completedCount++
        setProgressPercent(Math.round((completedCount / total) * 100))
        continue
      }

      if (!item.sourceText.trim()) {
        item.status = 'failed'
        item.error = `Trường '${sourceField}' rỗng`
        setItems([...batchItems])
        completedCount++
        setProgressPercent(Math.round((completedCount / total) * 100))
        continue
      }

      item.status = 'synthesizing'
      setItems([...batchItems])

      try {
        const wavBlob = await flamaAudioClient.synthesize({
          request_id: `req_${Date.now()}_${i}`,
          engine_id: engineId,
          language: isKokoro ? resolveLocaleFromVoiceId(selectedVoiceId) : 'ja-JP',
          voice_id: selectedVoiceId,
          text: item.sourceText,
          options: { speed, pitch, intonation: intonationScale, volume: volumeScale },
        })

        item.status = 'uploading'
        setItems([...batchItems])

        const res = await uploadNoteMediaBlob(
          item.noteId,
          destinationField,
          wavBlob,
          `${engineId}_${item.cardId}.wav`,
        )

        item.status = 'done'
        if (res.url) {
          updateCardFieldValuesInSessions(item.cardId, { [destinationField]: res.url })
        }
      } catch (err) {
        item.status = 'failed'
        item.error = err instanceof Error ? err.message : 'Tạo audio thất bại'
      }

      setItems([...batchItems])
      completedCount++
      setProgressPercent(Math.round((completedCount / total) * 100))
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

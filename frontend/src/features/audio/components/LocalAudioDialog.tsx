import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  Download,
  Layers,
  LoaderCircle,
  Play,
  RefreshCw,
  RotateCcw,
  Sliders,
  Volume2,
  XCircle,
} from 'lucide-react'
import { toast } from 'sonner'
import { resolveBackendUrl } from '@/config/env'
import { updateCardFieldValuesInSessions } from '@/features/study/session/sessionStore'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { apiRequest } from '@/shared/api/client'
import { uploadNoteMediaBlob } from '@/shared/api/noteMedia'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Progress } from '@/components/ui/progress'
import type { VoiceDescriptor } from '../types'

type LocalAudioDialogProps = {
  isOpen: boolean
  onClose: () => void
  selectedCardIds: string[]
  activeCardId?: string | null
  availableFieldNames?: string[]
  noteTypeName?: string
  engineId?: 'voicevox' | 'kokoro'
  defaultVoiceId?: string
  onSuccess?: () => void
}

type ProcessItemStatus = 'pending' | 'synthesizing' | 'uploading' | 'done' | 'failed' | 'skipped'

type BatchItem = {
  cardId: string
  noteId: string
  word: string
  sourceText: string
  status: ProcessItemStatus
  error?: string
}

type VoiceOption = {
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
  { id: '4', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'セクシー', label: '四国めたん (Metan) - セクシー' },
  { id: '36', speakerName: '四国めたん (Shikikoin Metan)', styleName: 'ささやき', label: '四国めたん (Metan) - ささやき' },
  { id: '8', speakerName: '春日部つむぎ (Kasukabe Tsumugi)', styleName: 'ノーマル', label: '春日部つむぎ (Tsumugi) - ノーマル' },
  { id: '10', speakerName: '波音リツ (Namine Ritsu)', styleName: 'ノーマル', label: '波音リツ (Ritsu) - ノーマル' },
  { id: '9', speakerName: '雨晴はう (Amehare Hau)', styleName: 'ノーマル', label: '雨晴はう (Hau) - ノーマル' },
  { id: '14', speakerName: '冥鳴ひまり (Meimei Himari)', styleName: 'ノーマル', label: '冥鳴ひまり (Himari) - ノーマル' },
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

export function LocalAudioDialog({
  isOpen,
  onClose,
  selectedCardIds,
  activeCardId,
  availableFieldNames = ['Reading', 'Word', 'Meaning', 'Audio'],
  noteTypeName,
  engineId = 'voicevox',
  defaultVoiceId,
  onSuccess,
}: LocalAudioDialogProps) {
  const isKokoro = engineId === 'kokoro'

  // Target Card Resolution
  const targetCardIds =
    selectedCardIds.length > 0 ? selectedCardIds : activeCardId ? [activeCardId] : []

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

  // Fetch card details dynamically if fields are missing or generic
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

  // Synchronize Source and Destination fields whenever dynamicFields or isOpen changes
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

  // Formatted Voice Options List & Grouped Mapping
  const voiceOptions = useMemo<VoiceOption[]>(() => {
    let rawOptions: VoiceOption[] = []
    if (voices.length > 0) {
      rawOptions = voices.map((v) => formatVoiceOption(v))
    } else {
      rawOptions = isKokoro ? FALLBACK_KOKORO_SPEAKERS : FALLBACK_VOICEVOX_SPEAKERS
    }

    // Filter Kokoro voice options to only show the selected language group from the dropdown
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
        // Group Kokoro voices by language category with flag icons
        const prefix = opt.id ? opt.id[0].toLowerCase() : 'a'
        switch (prefix) {
          case 'a':
            key = '🇺🇸 English (US)'
            break
          case 'b':
            key = '🇬🇧 English (UK)'
            break
          case 'z':
            key = '🇨🇳 Mandarin Chinese (中文)'
            break
          case 'e':
            key = '🇪🇸 Spanish (Español)'
            break
          case 'f':
            key = '🇫🇷 French (Français)'
            break
          case 'h':
            key = '🇮🇳 Hindi (हिन्दी)'
            break
          case 'i':
            key = '🇮🇹 Italian (Italiano)'
            break
          case 'p':
            key = '🇧🇷 Portuguese (Português)'
            break
          default:
            key = '🌐 Other Languages'
        }
      }
      if (!groups[key]) groups[key] = []
      groups[key].push(opt)
    }
    return groups
  }, [voiceOptions, isKokoro])

  // Ensure selectedVoiceId is valid
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

  // Reset Sliders to Defaults
  const handleResetDefaults = () => {
    setVolumeScale(1.0)
    setPitch(0.0)
    setSpeed(1.0)
    setIntonationScale(1.0)
    toast.info('Đã khôi phục thông số âm thanh mặc định.')
  }

  // Check Flama Audio Local Service
  const checkHealthAndInit = async () => {
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
  }

  useEffect(() => {
    if (isOpen) {
      checkHealthAndInit()
    }
  }, [isOpen, engineId])

  // Start Pairing Request
  const handleStartPairing = async () => {
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
        } catch {
          // Keep polling during 40 attempts window
        }
      }, 1500)
    } catch {
      toast.error('Không thể gửi yêu cầu ghép nối tới local service.')
    }
  }

  // Preview Audio Synthesis
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

  // Batch Audio Synthesis Execution
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

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-3xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-xl sm:rounded-2xl border-border/60 shadow-2xl">
        {/* Modal Header */}
        <DialogHeader className="px-3.5 sm:px-6 py-3 sm:py-4 border-b bg-muted/20 shrink-0 text-left">
          <div className="flex items-center justify-between gap-2">
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
              <Volume2 className="size-4 sm:size-5 text-primary shrink-0" />
              <span>Tạo âm thanh &gt; {isKokoro ? 'Đa ngôn ngữ Offline' : 'Tiếng Nhật Offline'}</span>
            </DialogTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs gap-1.5 border-primary/30 text-primary hover:bg-primary/10 font-semibold"
                asChild
              >
                <Link to="/guide/flama-audio" target="_blank">
                  <Download className="size-3.5" />
                  <span>Hướng dẫn &amp; Tải App</span>
                </Link>
              </Button>
              <Badge
                variant="outline"
                className="text-[11px] sm:text-xs font-semibold bg-emerald-500/10 text-emerald-600 border-emerald-500/30 px-2 py-0.5 shrink-0"
              >
                {targetCardIds.length} thẻ
              </Badge>
            </div>
          </div>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Tổng hợp giọng phát âm tự nhiên trực tiếp không cần mạng Internet thông qua ứng dụng Flama Audio Desktop.
          </DialogDescription>
        </DialogHeader>

        {/* Modal Body Scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 text-xs min-h-0">
          {/* Target Card Scope Banner */}
          <div className="p-4 rounded-xl bg-muted/40 border border-border/60 flex items-center justify-between shadow-xs">
            <span className="font-semibold text-foreground text-xs">
              Phạm vi áp dụng:{' '}
              <strong className="text-primary font-bold ml-1">
                {selectedCardIds.length > 0
                  ? `${selectedCardIds.length} thẻ đã tick chọn`
                  : activeCardId
                    ? '1 thẻ đang chọn trong bảng'
                    : 'Chưa chọn thẻ nào trong bảng'}
              </strong>
            </span>
            <Badge
              variant={targetCardIds.length > 0 ? 'default' : 'destructive'}
              className="text-[11px] px-2.5 py-0.5"
            >
              {targetCardIds.length > 0 ? `${targetCardIds.length} thẻ` : 'Chưa chọn'}
            </Badge>
          </div>

          {/* Service Connection Status Banners */}
          {serviceStatus === 'checking' && (
            <div className="flex items-center gap-2 p-3.5 bg-muted/50 rounded-xl text-xs">
              <LoaderCircle className="size-4 animate-spin text-primary" />
              Đang kết nối tới ứng dụng phát âm Flama Audio Desktop...
            </div>
          )}

          {serviceStatus === 'offline' && (
            <Alert variant="destructive" className="rounded-xl">
              <AlertCircle className="size-4" />
              <AlertTitle className="font-bold">Chưa mở ứng dụng phát âm Flama Audio</AlertTitle>
              <AlertDescription className="text-xs">
                Vui lòng khởi động <strong>Flama Audio Desktop</strong> trên máy tính của bạn, hoặc tải bản portable nếu chưa có.
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Button size="sm" variant="default" className="h-7 text-xs bg-primary text-primary-foreground font-medium" asChild>
                    <a href={resolveBackendUrl('/api/download/flama-audio')} target="_blank" rel="noopener noreferrer" download>
                      <Download className="size-3 mr-1.5" /> Tải Flama Audio Portable (.exe)
                    </a>
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs" asChild>
                    <Link to="/guide/flama-audio" target="_blank">
                      Xem hướng dẫn chi tiết
                    </Link>
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={checkHealthAndInit}>
                    <RefreshCw className="size-3 mr-1" /> Thử lại kết nối
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {serviceStatus === 'online' && !isPairingApproved && (
            <Alert variant="default" className="rounded-xl border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200">
              <Cpu className="size-4 text-amber-600" />
              <AlertTitle className="font-bold">Chờ xác nhận kết nối</AlertTitle>
              <AlertDescription className="text-xs text-amber-800 dark:text-amber-300">
                Bấm nút bên dưới để gửi yêu cầu kết nối, sau chọn <strong>Phê duyệt (Approve)</strong> trên phần mềm Flama Audio Desktop.
                <div className="mt-2.5">
                  <Button size="sm" className="h-7 text-xs" onClick={handleStartPairing} disabled={Boolean(pairingChallengeId)}>
                    {pairingChallengeId ? (
                      <>
                        <LoaderCircle className="size-3 mr-1 animate-spin" /> Đang chờ xác nhận...
                      </>
                    ) : (
                      'Kết nối ngay'
                    )}
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {engineOffline && (
            <Alert variant="default" className="rounded-xl border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200">
              <Cpu className="size-4 text-amber-600" />
              <AlertTitle className="font-bold">Giọng đọc Tiếng Nhật chưa sẵn sàng</AlertTitle>
              <AlertDescription className="text-xs text-amber-800 dark:text-amber-300">
                Bộ giọng đọc tiếng Nhật offline chưa sẵn sàng trên máy của bạn. Vui lòng bấm nút bên dưới để tự động tải về và thiết lập.
                
                {engineActionState === 'installing' && (
                  <div className="flex items-center gap-2 mt-3 p-2.5 bg-amber-500/15 rounded-lg font-medium text-amber-950 dark:text-amber-100">
                    <LoaderCircle className="size-4 animate-spin text-amber-600" />
                    Đang tải bộ giọng đọc tiếng Nhật (vui lòng chờ trong giây lát)...
                  </div>
                )}

                {engineActionState === 'launching' && (
                  <div className="flex items-center gap-2 mt-3 p-2.5 bg-amber-500/15 rounded-lg font-medium text-amber-950 dark:text-amber-100">
                    <LoaderCircle className="size-4 animate-spin text-amber-600" />
                    Đang khởi động giọng đọc tiếng Nhật...
                  </div>
                )}

                <div className="flex flex-wrap gap-2 mt-2.5">
                  <Button size="sm" className="h-7 text-xs bg-amber-600 hover:bg-amber-700 text-white" onClick={handleInstallEngine} disabled={engineActionState !== 'idle'}>
                    {engineActionState === 'installing' ? <LoaderCircle className="size-3 mr-1 animate-spin" /> : null}
                    Tải &amp; Tự động cài đặt giọng đọc
                  </Button>
                  <Button size="sm" variant="outline" className="h-7 text-xs border-amber-300 text-amber-800 dark:text-amber-200" onClick={handleLaunchEngine} disabled={engineActionState !== 'idle'}>
                    {engineActionState === 'launching' ? <LoaderCircle className="size-3 mr-1 animate-spin" /> : null}
                    Khởi động giọng đọc đã cài
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {/* Source & Destination Fields Row */}
          <div className="space-y-2">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="local-source-field" className="text-xs font-semibold text-foreground">
                  Trường nguồn đọc (Source Field)
                </Label>
                <NativeSelect
                  id="local-source-field"
                  className="w-full h-9 text-xs bg-background"
                  value={sourceField}
                  onChange={(e) => setSourceField(e.target.value)}
                  disabled={isProcessing}
                >
                  {dynamicFields.map((fn) => (
                    <NativeSelectOption key={`src-${fn}`} value={fn}>
                      {fn} {fn.toLowerCase() === 'reading' ? '(Khuyên dùng cho JP)' : ''}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="local-dest-field" className="text-xs font-semibold text-foreground">
                  Trường đích lưu Audio (Destination Field)
                </Label>
                <NativeSelect
                  id="local-dest-field"
                  className="w-full h-9 text-xs bg-background"
                  value={destinationField}
                  onChange={(e) => setDestinationField(e.target.value)}
                  disabled={isProcessing}
                >
                  {dynamicFields.map((fn) => (
                    <NativeSelectOption key={`dst-${fn}`} value={fn}>
                      {fn} {fn.toLowerCase() === 'audio' ? '(Mặc định lưu file)' : ''}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
            </div>

            {noteTypeName ? (
              <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                <span className="flex items-center gap-1">
                  <Layers className="size-3 text-primary shrink-0" />
                  <span>
                    Đang khớp trường theo loại thẻ: <strong className="text-foreground">{noteTypeName}</strong>
                  </span>
                </span>
                {sourceField === destinationField ? (
                  <span className="text-amber-600 dark:text-amber-400 font-semibold">
                    ⚠️ Trường nguồn và trường đích đang giống nhau
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>

          {/* Character / Voice Selection Row */}
          <div className="grid gap-4 sm:grid-cols-2 pt-4 border-t border-border/40">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="local-character" className="text-xs font-semibold text-foreground">
                Nhân vật / Giọng đọc ({isKokoro ? 'Kokoro Engine - Đa Ngôn Ngữ' : 'VOICEVOX Engine - Tiếng Nhật'})
              </Label>
              <NativeSelect
                id="local-character"
                className="w-full h-9 text-xs bg-background font-medium"
                value={selectedVoiceId}
                onChange={(e) => setSelectedVoiceId(e.target.value)}
                disabled={isProcessing}
              >
                {Object.entries(groupedVoiceOptions).map(([speaker, options]) => (
                  <optgroup key={speaker} label={`🎤 ${speaker}`}>
                    {options.map((opt) => (
                      <NativeSelectOption key={opt.id} value={opt.id}>
                        {opt.label}
                      </NativeSelectOption>
                    ))}
                  </optgroup>
                ))}
              </NativeSelect>
            </div>
          </div>

          {/* Advanced Audio Sliders */}
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
                onClick={handleResetDefaults}
                disabled={isProcessing}
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
                    {volumeScale.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.01"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={volumeScale}
                  onChange={(e) => setVolumeScale(parseFloat(e.target.value))}
                  disabled={isProcessing}
                />
              </div>

              {/* Pitch */}
              <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                <div className="flex items-center justify-between text-xs font-medium text-foreground">
                  <span>Cao độ</span>
                  <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                    {pitch.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="-0.4"
                  max="0.4"
                  step="0.01"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={pitch}
                  onChange={(e) => setPitch(parseFloat(e.target.value))}
                  disabled={isProcessing}
                />
              </div>

              {/* Speed */}
              <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                <div className="flex items-center justify-between text-xs font-medium text-foreground">
                  <span>Tốc độ đọc</span>
                  <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                    {speed.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="4"
                  step="0.01"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={speed}
                  onChange={(e) => setSpeed(parseFloat(e.target.value))}
                  disabled={isProcessing}
                />
              </div>

              {/* Intonation */}
              <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
                <div className="flex items-center justify-between text-xs font-medium text-foreground">
                  <span>Ngữ điệu</span>
                  <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                    {intonationScale.toFixed(2)}
                  </span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.01"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={intonationScale}
                  onChange={(e) => setIntonationScale(parseFloat(e.target.value))}
                  disabled={isProcessing}
                />
              </div>
            </div>
          </div>

          {/* Progress Indicator */}
          {isProcessing && (
            <div className="space-y-2 border p-4 rounded-xl bg-muted/30">
              <div className="flex justify-between text-xs font-semibold">
                <span>Đang tổng hợp phát âm VOICEVOX Local...</span>
                <span className="font-mono">{progressPercent}%</span>
              </div>
              <Progress value={progressPercent} className="h-2" />
            </div>
          )}

          {/* Batch Status List */}
          {items.length > 0 && (
            <div className="max-h-48 overflow-y-auto space-y-1.5 border rounded-xl p-2.5 bg-background">
              {items.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between text-xs p-2 rounded-lg hover:bg-muted/50 border border-border/40"
                >
                  <span className="font-semibold truncate max-w-[220px]">{item.word}</span>
                  <div className="flex items-center gap-2">
                    {item.status === 'pending' && <Badge variant="outline">Chờ xử lý</Badge>}
                    {item.status === 'synthesizing' && (
                      <Badge variant="secondary" className="gap-1 bg-primary/10 text-primary border-primary/20">
                        <LoaderCircle className="size-3 animate-spin" /> Sinh âm...
                      </Badge>
                    )}
                    {item.status === 'uploading' && (
                      <Badge variant="secondary" className="gap-1 bg-primary/10 text-primary border-primary/20">
                        <LoaderCircle className="size-3 animate-spin" /> Uploading...
                      </Badge>
                    )}
                    {item.status === 'done' && (
                      <Badge variant="default" className="bg-emerald-600 text-white gap-1">
                        <CheckCircle2 className="size-3" /> Thành công
                      </Badge>
                    )}
                    {item.status === 'skipped' && (
                      <Badge variant="outline" className="text-amber-600 border-amber-300">
                        Bỏ qua (Clone)
                      </Badge>
                    )}
                    {item.status === 'failed' && (
                      <Badge variant="destructive" className="gap-1" title={item.error}>
                        <XCircle className="size-3" /> Lỗi
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <DialogFooter className="px-4 sm:px-6 pt-4 pb-6 sm:pb-7 mb-0 border-t bg-muted/20 shrink-0 flex items-center justify-between gap-3">
          <Button variant="outline" size="sm" onClick={onClose} disabled={isProcessing}>
            Đóng
          </Button>

          <div className="flex items-center gap-2">
            {serviceStatus === 'online' && isPairingApproved && (
              <>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-9 text-xs gap-1.5"
                  onClick={handlePreviewAudio}
                  disabled={isPreviewing || isProcessing}
                >
                  {isPreviewing ? <LoaderCircle className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                  <span>Nghe thử phát âm</span>
                </Button>

                <Button
                  type="button"
                  size="sm"
                  className="h-9 text-xs gap-1.5"
                  onClick={handleStartBatch}
                  disabled={isProcessing || targetCardIds.length === 0}
                >
                  {isProcessing ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : (
                    <Volume2 className="size-3.5" />
                  )}
                  <span>Tạo audio ({targetCardIds.length} thẻ)</span>
                </Button>
              </>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

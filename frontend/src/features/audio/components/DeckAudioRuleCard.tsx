import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  Globe,
  LoaderCircle,
  Play,
  Plus,
  RotateCcw,
  Sliders,
  Trash2,
  Volume2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { flamaAudioClient } from '@/lib/flamaAudioClient'
import { resolveLocaleFromVoiceId } from '../services/ttsTextNormalizer'
import type { AudioRuleConfig, FieldMapping, VoiceDescriptor } from '../types'

const FALLBACK_VOICEVOX_SPEAKERS: Array<{ id: string; label: string; group: string }> = [
  { id: '3', label: 'ズンダモン (Zundamon) - ノーマル', group: 'ズンダモン (Zundamon)' },
  { id: '1', label: 'ズンダモン (Zundamon) - あまあま', group: 'ズンダモン (Zundamon)' },
  { id: '7', label: 'ズンダモン (Zundamon) - ツンツン', group: 'ズンダモン (Zundamon)' },
  { id: '5', label: 'ズンダモン (Zundamon) - セクシー', group: 'ズンダモン (Zundamon)' },
  { id: '22', label: 'ズンダモン (Zundamon) - ささやき', group: 'ズンダモン (Zundamon)' },
  { id: '38', label: 'ズンダモン (Zundamon) - ヒソヒソ', group: 'ズンダモン (Zundamon)' },
  { id: '2', label: '四国めたん (Metan) - ノーマル', group: '四国めたん (Metan)' },
  { id: '0', label: '四国めたん (Metan) - あまあま', group: '四国めたん (Metan)' },
  { id: '6', label: '四国めたん (Metan) - ツンツン', group: '四国めたん (Metan)' },
  { id: '4', label: '四国めたん (Metan) - セクシー', group: '四国めたん (Metan)' },
  { id: '36', label: '四国めたん (Metan) - ささやき', group: '四国めたん (Metan)' },
  { id: '8', label: '春日部つむぎ (Tsumugi) - ノーマル', group: '春日部つむぎ (Tsumugi)' },
  { id: '10', label: '波音リツ (Ritsu) - ノーマル', group: '波音リツ (Ritsu)' },
  { id: '9', label: '雨晴はう (Hau) - ノーマル', group: '雨晴はう (Hau)' },
  { id: '14', label: '冥鳴ひまり (Himari) - ノーマル', group: '冥鳴ひまり (Himari)' },
  { id: '16', label: '九州そら (Sora) - ノーマル', group: '九州そら (Sora)' },
  { id: '15', label: '九州そら (Sora) - あまあま', group: '九州そら (Sora)' },
  { id: '18', label: '九州そら (Sora) - ツンツン', group: '九州そら (Sora)' },
  { id: '17', label: '九州そら (Sora) - セクシー', group: '九州そら (Sora)' },
  { id: '20', label: 'もち子さん (Mochiko) - ノーマル', group: 'もち子さん (Mochiko)' },
  { id: '21', label: '剣崎雌雄 (Shiu) - ノーマル', group: '剣崎雌雄 (Shiu)' },
]

const FALLBACK_KOKORO_SPEAKERS: Array<{ id: string; label: string; group: string; lang: string }> = [
  { id: 'af_bella', label: 'Bella [English (US)] - Female', group: '🇺🇸 English (US)', lang: 'en-US' },
  { id: 'af_sarah', label: 'Sarah [English (US)] - Female', group: '🇺🇸 English (US)', lang: 'en-US' },
  { id: 'am_adam', label: 'Adam [English (US)] - Male', group: '🇺🇸 English (US)', lang: 'en-US' },
  { id: 'am_michael', label: 'Michael [English (US)] - Male', group: '🇺🇸 English (US)', lang: 'en-US' },
  { id: 'bf_emma', label: 'Emma [English (UK)] - Female', group: '🇬🇧 English (UK)', lang: 'en-GB' },
  { id: 'bm_george', label: 'George [English (UK)] - Male', group: '🇬🇧 English (UK)', lang: 'en-GB' },
  { id: 'zf_xiaobei', label: 'Xiaobei [Mandarin Chinese] - Female', group: '🇨🇳 Mandarin Chinese', lang: 'zh-CN' },
  { id: 'zm_yunjian', label: 'Yunjian [Mandarin Chinese] - Male', group: '🇨🇳 Mandarin Chinese', lang: 'zh-CN' },
  { id: 'ef_dora', label: 'Dora [Spanish] - Female', group: '🇪🇸 Spanish', lang: 'es-ES' },
  { id: 'ff_siwis', label: 'Siwis [French] - Female', group: '🇫🇷 French', lang: 'fr-FR' },
  { id: 'hf_alpha', label: 'Alpha [Hindi] - Female', group: '🇮🇳 Hindi', lang: 'hi-IN' },
  { id: 'if_sara', label: 'Sara [Italian] - Female', group: '🇮🇹 Italian', lang: 'it-IT' },
  { id: 'pf_dora', label: 'Dora [Portuguese] - Female', group: '🇧🇷 Portuguese', lang: 'pt-BR' },
]

const KOKORO_LANGUAGES = [
  { code: 'all', label: '🌐 Tất cả ngôn ngữ' },
  { code: 'en-US', label: '🇺🇸 Tiếng Anh (Mỹ) - English (US)' },
  { code: 'en-GB', label: '🇬🇧 Tiếng Anh (Anh) - English (UK)' },
  { code: 'zh-CN', label: '🇨🇳 Tiếng Trung - Mandarin Chinese' },
  { code: 'es-ES', label: '🇪🇸 Tiếng Tây Ban Nha - Spanish' },
  { code: 'fr-FR', label: '🇫🇷 Tiếng Pháp - French' },
  { code: 'ja-JP', label: '🇯🇵 Tiếng Nhật - Japanese' },
  { code: 'hi-IN', label: '🇮🇳 Tiếng Hindi' },
  { code: 'it-IT', label: '🇮🇹 Tiếng Ý - Italian' },
  { code: 'pt-BR', label: '🇧🇷 Tiếng Bồ Đào Nha - Portuguese' },
]

type DeckAudioRuleCardProps = {
  rule: AudioRuleConfig
  index: number
  availableFieldNames: string[]
  canDelete: boolean
  sampleWord?: string
  onUpdateRule: (ruleId: string, updater: Partial<AudioRuleConfig>) => void
  onDeleteRule: (ruleId: string) => void
  onAddMapping: (ruleId: string) => void
  onRemoveMapping: (ruleId: string, mappingId: string) => void
  onUpdateMapping: (ruleId: string, mappingId: string, updater: Partial<FieldMapping>) => void
}

export function DeckAudioRuleCard({
  rule,
  index,
  availableFieldNames,
  canDelete,
  sampleWord = 'こんにちは',
  onUpdateRule,
  onDeleteRule,
  onAddMapping,
  onRemoveMapping,
  onUpdateMapping,
}: DeckAudioRuleCardProps) {
  const [voices, setVoices] = useState<VoiceDescriptor[]>([])
  const [selectedLang, setSelectedLang] = useState<string>('all')
  const [previewText, setPreviewText] = useState(sampleWord || (rule.engineId === 'kokoro' ? 'Hello world' : 'こんにちは'))
  const [isPreviewing, setIsPreviewing] = useState(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

  // Fallback field names if none provided
  const fieldList = useMemo(() => {
    if (availableFieldNames.length > 0) return availableFieldNames
    return ['Word', 'Reading', 'Front', 'Expression', 'Back', 'Audio', 'FrontAudio', 'Reading_audio', 'Vietnamese']
  }, [availableFieldNames])

  // Fetch available voices for current engine
  useEffect(() => {
    let isMounted = true
    flamaAudioClient
      .getVoices(rule.engineId)
      .then((res) => {
        if (isMounted && res.length > 0) {
          setVoices(res)
        }
      })
      .catch(() => {})
    return () => {
      isMounted = false
    }
  }, [rule.engineId])

  // Grouped voice options matching Browse and filtered by selected language
  const groupedVoices = useMemo(() => {
    const isKokoro = rule.engineId === 'kokoro'
    if (voices.length > 0) {
      const groups: Record<string, Array<{ id: string; label: string; lang: string }>> = {}
      for (const v of voices) {
        let groupName = v.speaker_name || 'VOICEVOX'
        let langCode = 'ja-JP'
        if (isKokoro) {
          const prefix = v.voice_id ? v.voice_id[0].toLowerCase() : 'a'
          switch (prefix) {
            case 'a': groupName = '🇺🇸 English (US)'; langCode = 'en-US'; break
            case 'b': groupName = '🇬🇧 English (UK)'; langCode = 'en-GB'; break
            case 'z': groupName = '🇨🇳 Mandarin Chinese'; langCode = 'zh-CN'; break
            case 'e': groupName = '🇪🇸 Spanish'; langCode = 'es-ES'; break
            case 'f': groupName = '🇫🇷 French'; langCode = 'fr-FR'; break
            case 'h': groupName = '🇮🇳 Hindi'; langCode = 'hi-IN'; break
            case 'i': groupName = '🇮🇹 Italian'; langCode = 'it-IT'; break
            case 'p': groupName = '🇧🇷 Portuguese'; langCode = 'pt-BR'; break
            case 'j': groupName = '🇯🇵 Japanese'; langCode = 'ja-JP'; break
            default: groupName = '🌐 Other Languages'; langCode = 'other'; break
          }
        }

        // Apply language filter
        if (isKokoro && selectedLang !== 'all' && langCode !== selectedLang) {
          continue
        }

        if (!groups[groupName]) groups[groupName] = []
        groups[groupName].push({
          id: v.voice_id,
          label: `${v.speaker_name || ''} ${v.style_name ? `(${v.style_name})` : ''}`.trim() || v.name || v.voice_id,
          lang: langCode,
        })
      }
      return groups
    }

    // Fallback
    const fallbackList = isKokoro ? FALLBACK_KOKORO_SPEAKERS : FALLBACK_VOICEVOX_SPEAKERS
    const groups: Record<string, Array<{ id: string; label: string; lang?: string }>> = {}
    for (const item of fallbackList) {
      const itemLang = (item as any).lang || 'ja-JP'
      if (isKokoro && selectedLang !== 'all' && itemLang !== selectedLang) {
        continue
      }
      if (!groups[item.group]) groups[item.group] = []
      groups[item.group].push({ id: item.id, label: item.label, lang: itemLang })
    }
    return groups
  }, [voices, rule.engineId, selectedLang])

  // When language filter changes and current voice is not in filtered list, auto-select first available
  const handleLanguageChange = (newLang: string) => {
    setSelectedLang(newLang)
    if (newLang === 'all') return

    // Find first voice matching this language
    const isKokoro = rule.engineId === 'kokoro'
    if (isKokoro) {
      let targetPrefix = 'a'
      switch (newLang) {
        case 'en-US': targetPrefix = 'a'; break
        case 'en-GB': targetPrefix = 'b'; break
        case 'zh-CN': targetPrefix = 'z'; break
        case 'es-ES': targetPrefix = 'e'; break
        case 'fr-FR': targetPrefix = 'f'; break
        case 'hi-IN': targetPrefix = 'h'; break
        case 'it-IT': targetPrefix = 'i'; break
        case 'pt-BR': targetPrefix = 'p'; break
        case 'ja-JP': targetPrefix = 'j'; break
      }

      const matchingVoice = voices.find((v) => v.voice_id?.toLowerCase().startsWith(targetPrefix))
        || FALLBACK_KOKORO_SPEAKERS.find((v) => v.lang === newLang)

      if (matchingVoice) {
        const nextId = 'voice_id' in matchingVoice ? (matchingVoice.voice_id as string) : matchingVoice.id
        if (nextId) {
          onUpdateRule(rule.id, { voiceId: nextId })
        }
      }
    }
  }

  const handleResetSliders = () => {
    onUpdateRule(rule.id, {
      speed: 1.0,
      pitch: 0.0,
      intonation: 1.0,
      volume: 1.0,
    })
    toast.info('Đã khôi phục thông số giọng đọc mặc định.')
  }

  const handlePreview = async () => {
    setIsPreviewing(true)
    try {
      const textToSynthesize = previewText.trim() || (rule.engineId === 'kokoro' ? 'Hello' : 'こんにちは')
      const wavBlob = await flamaAudioClient.synthesize({
        request_id: `preview_${Date.now()}`,
        engine_id: rule.engineId,
        language: rule.engineId === 'kokoro' ? resolveLocaleFromVoiceId(rule.voiceId) : 'ja-JP',
        voice_id: rule.voiceId,
        text: textToSynthesize,
        options: {
          speed: rule.speed,
          pitch: rule.pitch,
          intonation: rule.intonation,
          volume: rule.volume,
        },
      })

      const url = URL.createObjectURL(wavBlob)
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause()
      }
      const audio = new Audio(url)
      audioPlayerRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(url)
        setIsPreviewing(false)
      }
      await audio.play()
    } catch (err) {
      setIsPreviewing(false)
      toast.error(err instanceof Error ? err.message : 'Nghe thử phát âm thất bại.')
    }
  }

  return (
    <Card className="rounded-2xl border-border/70 shadow-xs overflow-hidden">
      <CardHeader className="p-4 sm:p-5 border-b bg-muted/20 flex flex-row items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex size-6 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold text-primary">
            #{index + 1}
          </span>
          <CardTitle className="text-sm sm:text-base font-bold text-foreground">
            {rule.name}
          </CardTitle>
        </div>

        {canDelete && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDeleteRule(rule.id)}
            className="h-8 text-xs text-destructive hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="size-3.5 mr-1" />
            <span>Xóa cấu hình</span>
          </Button>
        )}
      </CardHeader>

      <CardContent className="p-4 sm:p-5 space-y-5">
        {/* Engine, Language Filter & Voice Grid */}
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {/* Engine Selector */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Công cụ phát âm (TTS Engine)</Label>
            <NativeSelect
              value={rule.engineId}
              onChange={(e) => {
                const nextEngine = e.target.value as 'voicevox' | 'kokoro'
                const defaultVoice = nextEngine === 'kokoro' ? 'af_bella' : '3'
                setSelectedLang('all')
                onUpdateRule(rule.id, { engineId: nextEngine, voiceId: defaultVoice })
              }}
              className="h-10 text-xs sm:text-sm rounded-xl"
            >
              <option value="voicevox">VOICEVOX (Tiếng Nhật tự nhiên Offline)</option>
              <option value="kokoro">Kokoro-82M (Đa ngôn ngữ Offline)</option>
            </NativeSelect>
          </div>

          {/* Language Filter */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold flex items-center gap-1">
              <Globe className="size-3.5 text-primary" />
              <span>Ngôn ngữ (Language)</span>
            </Label>
            {rule.engineId === 'kokoro' ? (
              <NativeSelect
                value={selectedLang}
                onChange={(e) => handleLanguageChange(e.target.value)}
                className="h-10 text-xs sm:text-sm rounded-xl font-medium"
              >
                {KOKORO_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.label}
                  </option>
                ))}
              </NativeSelect>
            ) : (
              <NativeSelect
                value="ja-JP"
                disabled
                className="h-10 text-xs sm:text-sm rounded-xl bg-muted/40 font-medium"
              >
                <option value="ja-JP">🇯🇵 Tiếng Nhật (Japanese)</option>
              </NativeSelect>
            )}
          </div>

          {/* Voice Selector */}
          <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
            <Label className="text-xs font-semibold">Giọng phát âm ({rule.engineId === 'kokoro' ? 'Kokoro' : 'VOICEVOX'})</Label>
            <NativeSelect
              value={rule.voiceId}
              onChange={(e) => onUpdateRule(rule.id, { voiceId: e.target.value })}
              className="h-10 text-xs sm:text-sm rounded-xl"
            >
              {Object.keys(groupedVoices).length === 0 ? (
                <option value="">Không có giọng đọc phù hợp</option>
              ) : (
                Object.entries(groupedVoices).map(([groupName, groupItems]) => (
                  <optgroup key={groupName} label={groupName}>
                    {groupItems.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.label}
                      </option>
                    ))}
                  </optgroup>
                ))
              )}
            </NativeSelect>
          </div>
        </div>

        {/* Field Mappings Section */}
        <div className="space-y-3 rounded-xl border border-border/60 bg-muted/20 p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Volume2 className="size-4 text-primary" />
              <span className="text-xs font-bold text-foreground">
                Ánh xạ trường (Cột nguồn từ $\rightarrow$ Ghi file audio vào)
              </span>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onAddMapping(rule.id)}
              className="h-7 text-[11px] gap-1 border-primary/30 text-primary hover:bg-primary/10 font-semibold"
            >
              <Plus className="size-3" />
              <span>Thêm cặp trường</span>
            </Button>
          </div>

          <div className="space-y-2.5">
            {rule.mappings.map((m, mIdx) => (
              <div
                key={m.id}
                className="flex flex-col sm:flex-row items-center gap-2 rounded-xl bg-card p-3 border border-border/50 shadow-2xs"
              >
                <div className="flex-1 w-full space-y-1">
                  <span className="text-[11px] font-semibold text-muted-foreground">
                    Cột nguồn từ #{mIdx + 1}:
                  </span>
                  <NativeSelect
                    value={m.sourceField}
                    onChange={(e) =>
                      onUpdateMapping(rule.id, m.id, { sourceField: e.target.value })
                    }
                    className="h-9 text-xs sm:text-sm rounded-xl"
                  >
                    {fieldList.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </NativeSelect>
                </div>

                <div className="hidden sm:flex items-center justify-center pt-4">
                  <ArrowRight className="size-4 text-muted-foreground" />
                </div>

                <div className="flex-1 w-full space-y-1">
                  <span className="text-[11px] font-semibold text-muted-foreground">
                    Ghi file audio vào:
                  </span>
                  <NativeSelect
                    value={m.destinationField}
                    onChange={(e) =>
                      onUpdateMapping(rule.id, m.id, { destinationField: e.target.value })
                    }
                    className="h-9 text-xs sm:text-sm rounded-xl"
                  >
                    {fieldList.map((f) => (
                      <option key={f} value={f}>
                        {f}
                      </option>
                    ))}
                  </NativeSelect>
                </div>

                {rule.mappings.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => onRemoveMapping(rule.id, m.id)}
                    className="h-8 self-end sm:self-center mt-2 sm:mt-4 text-destructive hover:bg-destructive/10"
                    title="Xóa cặp trường"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Sliders Block (Identical to Browse AudioAdvancedSettings) */}
        <div className="space-y-2.5 pt-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-foreground">
              <Sliders className="size-4 text-primary" />
              <span>Cấu hình thông số giọng đọc nâng cao</span>
            </div>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleResetSliders}
              className="h-8 text-xs font-semibold text-muted-foreground hover:text-primary gap-1"
            >
              <RotateCcw className="size-3.5" />
              <span>Khôi phục mặc định</span>
            </Button>
          </div>

          <div className="grid gap-3.5 sm:grid-cols-2 pt-1">
            {/* Volume Scale */}
            <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
              <div className="flex items-center justify-between text-xs font-medium text-foreground">
                <span>Âm lượng</span>
                <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                  {rule.volume.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.01"
                className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                value={rule.volume}
                onChange={(e) => onUpdateRule(rule.id, { volume: parseFloat(e.target.value) })}
              />
            </div>

            {/* Pitch */}
            <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
              <div className="flex items-center justify-between text-xs font-medium text-foreground">
                <span>Cao độ</span>
                <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                  {rule.pitch.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="-0.4"
                max="0.4"
                step="0.01"
                className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                value={rule.pitch}
                onChange={(e) => onUpdateRule(rule.id, { pitch: parseFloat(e.target.value) })}
              />
            </div>

            {/* Speed */}
            <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
              <div className="flex items-center justify-between text-xs font-medium text-foreground">
                <span>Tốc độ đọc</span>
                <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                  {rule.speed.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0.1"
                max="4"
                step="0.01"
                className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                value={rule.speed}
                onChange={(e) => onUpdateRule(rule.id, { speed: parseFloat(e.target.value) })}
              />
            </div>

            {/* Intonation */}
            <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
              <div className="flex items-center justify-between text-xs font-medium text-foreground">
                <span>Ngữ điệu</span>
                <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
                  {rule.intonation.toFixed(2)}
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="2"
                step="0.01"
                className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                value={rule.intonation}
                onChange={(e) => onUpdateRule(rule.id, { intonation: parseFloat(e.target.value) })}
              />
            </div>
          </div>
        </div>

        {/* Preview Voice Bar */}
        <div className="flex flex-col sm:flex-row items-center gap-2 pt-2 border-t">
          <Input
            value={previewText}
            onChange={(e) => setPreviewText(e.target.value)}
            placeholder="Nhập văn bản nghe thử phát âm..."
            className="h-9 text-xs rounded-xl flex-1"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePreview}
            disabled={isPreviewing}
            className="h-9 text-xs gap-1.5 w-full sm:w-auto shrink-0 font-semibold"
          >
            {isPreviewing ? (
              <LoaderCircle className="size-3.5 animate-spin text-primary" />
            ) : (
              <Play className="size-3.5 text-primary" />
            )}
            <span>Nghe thử phát âm</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

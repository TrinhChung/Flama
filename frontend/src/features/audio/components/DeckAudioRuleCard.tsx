import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
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

const FALLBACK_VOICEVOX_VOICES: Array<{ id: string; label: string; group: string }> = [
  { id: '3', label: 'ズンダモン (Zundamon) - ノーマル', group: 'ズンダモン (Zundamon)' },
  { id: '1', label: 'ズンダモン (Zundamon) - あまあま', group: 'ズンダモン (Zundamon)' },
  { id: '7', label: 'ズンダモン (Zundamon) - ツンツン', group: 'ズンダモン (Zundamon)' },
  { id: '5', label: 'ズンダモン (Zundamon) - セクシー', group: 'ズンダモン (Zundamon)' },
  { id: '2', label: '四国めたん (Metan) - ノーマル', group: '四国めたん (Metan)' },
  { id: '0', label: '四国めたん (Metan) - あまあま', group: '四国めたん (Metan)' },
  { id: '8', label: '春日部つむぎ (Tsumugi) - ノーマル', group: '春日部つむぎ (Tsumugi)' },
  { id: '10', label: '波音リツ (Ritsu) - ノーマル', group: '波音リツ (Ritsu)' },
  { id: '14', label: '冥鳴ひまり (Himari) - ノーマル', group: '冥鳴ひまり (Himari)' },
  { id: '16', label: '九州そら (Sora) - ノーマル', group: '九州そら (Sora)' },
]

const FALLBACK_KOKORO_VOICES: Array<{ id: string; label: string; group: string }> = [
  { id: 'af_bella', label: 'Bella [English (US)] - Female', group: '🇺🇸 English (US)' },
  { id: 'af_sarah', label: 'Sarah [English (US)] - Female', group: '🇺🇸 English (US)' },
  { id: 'am_adam', label: 'Adam [English (US)] - Male', group: '🇺🇸 English (US)' },
  { id: 'bf_emma', label: 'Emma [English (UK)] - Female', group: '🇬🇧 English (UK)' },
  { id: 'zf_xiaobei', label: 'Xiaobei [Mandarin Chinese] - Female', group: '🇨🇳 Mandarin Chinese' },
  { id: 'ef_dora', label: 'Dora [Spanish] - Female', group: '🇪🇸 Spanish' },
  { id: 'ff_siwis', label: 'Siwis [French] - Female', group: '🇫🇷 French' },
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
  const [previewText, setPreviewText] = useState(sampleWord || (rule.engineId === 'kokoro' ? 'Hello world' : 'こんにちは'))
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [showAdvancedSliders, setShowAdvancedSliders] = useState(false)
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null)

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

  // Grouped voice options
  const groupedVoices = useMemo(() => {
    const isKokoro = rule.engineId === 'kokoro'
    if (voices.length > 0) {
      const groups: Record<string, Array<{ id: string; label: string }>> = {}
      for (const v of voices) {
        let groupName = v.speaker_name || 'VOICEVOX'
        if (isKokoro) {
          const prefix = v.voice_id ? v.voice_id[0].toLowerCase() : 'a'
          switch (prefix) {
            case 'a': groupName = '🇺🇸 English (US)'; break
            case 'b': groupName = '🇬🇧 English (UK)'; break
            case 'z': groupName = '🇨🇳 Mandarin Chinese'; break
            case 'e': groupName = '🇪🇸 Spanish'; break
            case 'f': groupName = '🇫🇷 French'; break
            case 'h': groupName = '🇮🇳 Hindi'; break
            case 'i': groupName = '🇮🇹 Italian'; break
            case 'p': groupName = '🇧🇷 Portuguese'; break
            default: groupName = '🌐 Other Languages'
          }
        }
        if (!groups[groupName]) groups[groupName] = []
        groups[groupName].push({
          id: v.voice_id,
          label: `${v.speaker_name || ''} ${v.style_name ? `(${v.style_name})` : ''}`.trim() || v.name || v.voice_id,
        })
      }
      return groups
    }

    // Fallback
    const fallbackList = isKokoro ? FALLBACK_KOKORO_VOICES : FALLBACK_VOICEVOX_VOICES
    const groups: Record<string, Array<{ id: string; label: string }>> = {}
    for (const item of fallbackList) {
      if (!groups[item.group]) groups[item.group] = []
      groups[item.group].push({ id: item.id, label: item.label })
    }
    return groups
  }, [voices, rule.engineId])

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
        {/* Engine & Voice Grid */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* Engine Selector */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Công cụ phát âm (TTS Engine)</Label>
            <NativeSelect
              value={rule.engineId}
              onChange={(e) => {
                const nextEngine = e.target.value as 'voicevox' | 'kokoro'
                const defaultVoice = nextEngine === 'kokoro' ? 'af_bella' : '3'
                onUpdateRule(rule.id, { engineId: nextEngine, voiceId: defaultVoice })
              }}
              className="h-9 text-xs rounded-xl"
            >
              <option value="voicevox">VOICEVOX (Tiếng Nhật tự nhiên Offline)</option>
              <option value="kokoro">Kokoro-82M (Đa ngôn ngữ: Anh, Trung, Tây Ban Nha, Pháp...)</option>
            </NativeSelect>
          </div>

          {/* Voice Selector */}
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Giọng đọc (Voice / Speaker)</Label>
            <NativeSelect
              value={rule.voiceId}
              onChange={(e) => onUpdateRule(rule.id, { voiceId: e.target.value })}
              className="h-9 text-xs rounded-xl"
            >
              {Object.entries(groupedVoices).map(([groupName, groupItems]) => (
                <optgroup key={groupName} label={groupName}>
                  {groupItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </NativeSelect>
          </div>
        </div>

        {/* Field Mappings Section */}
        <div className="space-y-3 rounded-xl border border-border/60 bg-muted/20 p-3.5 sm:p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Volume2 className="size-4 text-primary" />
              <span className="text-xs font-bold text-foreground">
                Ánh xạ trường (Cột nguồn chữ $\rightarrow$ Cột ghi file âm thanh)
              </span>
            </div>

            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onAddMapping(rule.id)}
              className="h-7 text-[11px] gap-1 border-primary/30 text-primary hover:bg-primary/10"
            >
              <Plus className="size-3" />
              <span>Thêm cặp trường</span>
            </Button>
          </div>

          <div className="space-y-2.5">
            {rule.mappings.map((m, mIdx) => (
              <div
                key={m.id}
                className="flex flex-col sm:flex-row items-center gap-2 rounded-lg bg-card p-2.5 border border-border/50 shadow-2xs"
              >
                <div className="flex-1 w-full space-y-1">
                  <span className="text-[11px] font-medium text-muted-foreground">
                    Trường nguồn (chữ) #{mIdx + 1}:
                  </span>
                  <NativeSelect
                    value={m.sourceField}
                    onChange={(e) =>
                      onUpdateMapping(rule.id, m.id, { sourceField: e.target.value })
                    }
                    className="h-8 text-xs rounded-lg"
                  >
                    {availableFieldNames.map((f) => (
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
                  <span className="text-[11px] font-medium text-muted-foreground">
                    Ghi file audio vào trường:
                  </span>
                  <NativeSelect
                    value={m.destinationField}
                    onChange={(e) =>
                      onUpdateMapping(rule.id, m.id, { destinationField: e.target.value })
                    }
                    className="h-8 text-xs rounded-lg"
                  >
                    {availableFieldNames.map((f) => (
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
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Sliders Accordion Toggle */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowAdvancedSliders(!showAdvancedSliders)}
              className="h-7 text-xs font-semibold gap-1.5 text-muted-foreground hover:text-foreground"
            >
              <Sliders className="size-3.5" />
              <span>{showAdvancedSliders ? 'Ẩn thông số nâng cao' : 'Tùy chỉnh tốc độ, cao độ, ngữ điệu'}</span>
            </Button>

            {showAdvancedSliders && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={handleResetSliders}
                className="h-7 text-xs gap-1 text-muted-foreground hover:text-primary"
              >
                <RotateCcw className="size-3" />
                <span>Mặc định</span>
              </Button>
            )}
          </div>

          {showAdvancedSliders && (
            <div className="grid gap-3.5 sm:grid-cols-2 rounded-xl border border-border/50 bg-muted/10 p-4">
              {/* Speed */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold">Tốc độ nói (Speed)</span>
                  <span className="font-mono text-primary font-bold">{rule.speed.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.05"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={rule.speed}
                  onChange={(e) => onUpdateRule(rule.id, { speed: parseFloat(e.target.value) })}
                />
              </div>

              {/* Pitch */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold">Cao độ (Pitch)</span>
                  <span className="font-mono text-primary font-bold">{rule.pitch.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="-0.15"
                  max="0.15"
                  step="0.01"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={rule.pitch}
                  onChange={(e) => onUpdateRule(rule.id, { pitch: parseFloat(e.target.value) })}
                />
              </div>

              {/* Intonation */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold">Ngữ điệu (Intonation)</span>
                  <span className="font-mono text-primary font-bold">{rule.intonation.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="2.0"
                  step="0.05"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={rule.intonation}
                  onChange={(e) => onUpdateRule(rule.id, { intonation: parseFloat(e.target.value) })}
                />
              </div>

              {/* Volume */}
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="font-semibold">Âm lượng (Volume)</span>
                  <span className="font-mono text-primary font-bold">{rule.volume.toFixed(2)}x</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="2.0"
                  step="0.05"
                  className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  value={rule.volume}
                  onChange={(e) => onUpdateRule(rule.id, { volume: parseFloat(e.target.value) })}
                />
              </div>
            </div>
          )}
        </div>

        {/* Preview Voice Bar */}
        <div className="flex flex-col sm:flex-row items-center gap-2 pt-1 border-t">
          <Input
            value={previewText}
            onChange={(e) => setPreviewText(e.target.value)}
            placeholder="Nhập văn bản nghe thử phát âm..."
            className="h-8 text-xs rounded-lg flex-1"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePreview}
            disabled={isPreviewing}
            className="h-8 text-xs gap-1.5 w-full sm:w-auto shrink-0"
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

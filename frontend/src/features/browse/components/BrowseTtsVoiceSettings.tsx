import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'

export interface BrowseTtsVoiceSettingsProps {
  ttsVolumeScale: number
  setTtsVolumeScale: (val: number) => void
  ttsPitch: number
  setTtsPitch: (val: number) => void
  ttsSpeed: number
  setTtsSpeed: (val: number) => void
  ttsIntonationScale: number
  setTtsIntonationScale: (val: number) => void
  ttsInitialSilence: number
  setTtsInitialSilence: (val: number) => void
  ttsFinalSilence: number
  setTtsFinalSilence: (val: number) => void
  ttsAppendAudio: boolean
  setTtsAppendAudio: (val: boolean) => void
  ttsUseOpus: boolean
  setTtsUseOpus: (val: boolean) => void
  handleResetTtsDefaults: () => void
}

export function BrowseTtsVoiceSettings({
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
  ttsAppendAudio,
  setTtsAppendAudio,
  ttsUseOpus,
  setTtsUseOpus,
  handleResetTtsDefaults,
}: BrowseTtsVoiceSettingsProps) {
  const { t } = useTranslation('browse')

  return (
    <>
      {/* Voice Advanced tuning Sliders */}
      <div className="space-y-3.5 pt-1">
        <div className="flex items-center justify-between text-xs font-bold">
          <span>{t('tts_modal.advanced_title')}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetTtsDefaults}
            className="h-7 text-[10px] text-muted-foreground hover:text-primary rounded-md font-semibold"
          >
            {t('tts_modal.reset_defaults')}
          </Button>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2">
          {/* Volume Scale */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.volume_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsVolumeScale.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsVolumeScale}
              onChange={(e) => setTtsVolumeScale(parseFloat(e.target.value))}
            />
          </div>

          {/* Pitch */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.pitch_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsPitch.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="-0.15"
              max="0.15"
              step="0.01"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsPitch}
              onChange={(e) => setTtsPitch(parseFloat(e.target.value))}
            />
          </div>

          {/* Speed */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.speed_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsSpeed.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0.5"
              max="1.5"
              step="0.05"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsSpeed}
              onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
            />
          </div>

          {/* Intonation Scale */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.intonation_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsIntonationScale.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="2"
              step="0.05"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsIntonationScale}
              onChange={(e) => setTtsIntonationScale(parseFloat(e.target.value))}
            />
          </div>
        </div>

        <div className="grid gap-3.5 sm:grid-cols-2">
          {/* Initial Silence */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.initial_silence_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsInitialSilence.toFixed(2)}s
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1.5"
              step="0.05"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsInitialSilence}
              onChange={(e) => setTtsInitialSilence(parseFloat(e.target.value))}
            />
          </div>

          {/* Final Silence */}
          <div className="p-3 bg-muted/20 border rounded-xl space-y-1.5 hover:border-primary/30 transition-colors">
            <div className="flex items-center justify-between text-[11px] font-medium text-foreground">
              <span>{t('tts_modal.final_silence_label')}</span>
              <span className="font-mono font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-md">
                {ttsFinalSilence.toFixed(2)}s
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1.5"
              step="0.05"
              className="w-full h-1 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              value={ttsFinalSilence}
              onChange={(e) => setTtsFinalSilence(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 pt-1 text-xs">
        <label className="flex items-center gap-2 cursor-pointer font-medium">
          <Checkbox
            checked={ttsAppendAudio}
            onCheckedChange={(checked) => setTtsAppendAudio(Boolean(checked))}
          />
          <span>{t('tts_modal.append_audio_label')}</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer font-medium">
          <Checkbox
            checked={ttsUseOpus}
            onCheckedChange={(checked) => setTtsUseOpus(Boolean(checked))}
          />
          <span>{t('tts_modal.use_opus_label')}</span>
        </label>
      </div>
    </>
  )
}

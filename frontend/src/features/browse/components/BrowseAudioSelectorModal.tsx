import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  ChevronRight,
  Cloud,
  Cpu,
  Globe,
  Layers,
  Volume2,
} from 'lucide-react'

import { loadStoredLocalAudioSettings } from '@/features/audio/services/localAudioStorage'
import { loadStoredBrowseTtsSettings } from '../services/ttsSettingsStorage'

export interface BrowseAudioSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  onSelectWebVoiceVox: () => void
  onSelectLocalVoice: (engineId: 'voicevox' | 'kokoro', defaultVoiceId: string) => void
  selectedCardCount?: number
}

const KOKORO_VOICE_CONFIGS = [
  { id: 'af_bella', lang: 'en', flag: '🇺🇸/🇬🇧', labelKey: 'en' },
  { id: 'zf_xiaobei', lang: 'zh', flag: '🇨🇳', labelKey: 'zh' },
  { id: 'ef_dora', lang: 'es', flag: '🇪🇸', labelKey: 'es' },
  { id: 'ff_siwis', lang: 'fr', flag: '🇫🇷', labelKey: 'fr' },
  { id: 'if_sara', lang: 'it', flag: '🇮🇹', labelKey: 'it' },
  { id: 'pf_dora', lang: 'pt', flag: '🇧🇷', labelKey: 'pt' },
  { id: 'hf_alpha', lang: 'hi', flag: '🇮🇳', labelKey: 'hi' },
] as const

export function BrowseAudioSelectorModal({
  isOpen,
  onClose,
  onSelectWebVoiceVox,
  onSelectLocalVoice,
  selectedCardCount = 0,
}: BrowseAudioSelectorModalProps) {
  const { t } = useTranslation('browse')
  const localSettings = loadStoredLocalAudioSettings()
  const webTtsSettings = loadStoredBrowseTtsSettings()
  const targetVoicevoxId = localSettings.lastVoiceIdVoicevox || '3'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[94vw] sm:max-w-lg max-h-[88vh] flex flex-col p-0 rounded-2xl overflow-hidden border-border/60 shadow-2xl bg-card">
        {/* Modal Header */}
        <DialogHeader className="px-4 sm:px-6 py-3.5 sm:py-4 border-b border-border/60 bg-muted/20 shrink-0 text-left">
          <div className="flex items-center justify-between gap-2">
            <DialogTitle className="flex items-center gap-2.5 text-base sm:text-lg font-bold text-foreground">
              <div className="p-1.5 sm:p-2 rounded-xl bg-primary/10 text-primary shrink-0">
                <Volume2 className="size-4 sm:size-5" />
              </div>
              <span>{t('audio_selector.title')}</span>
            </DialogTitle>
            {selectedCardCount > 0 && (
              <Badge
                variant="outline"
                className="text-[11px] font-bold bg-primary/10 text-primary border-primary/25 rounded-full px-2.5 py-0.5 shrink-0"
              >
                {t('audio_selector.cards_count', { count: selectedCardCount })}
              </Badge>
            )}
          </div>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            {t('audio_selector.description')}
          </DialogDescription>
        </DialogHeader>

        {/* Modal Scrollable Body */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4 text-xs min-h-0">
          {/* Card Scope Banner */}
          {selectedCardCount > 0 && (
            <div className="flex items-center justify-between p-2.5 sm:p-3 rounded-xl bg-muted/30 border border-border/60">
              <span className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                <Layers className="size-3.5 text-primary" />
                <span>{t('audio_selector.scope_label')}</span>
              </span>
              <span className="font-semibold text-foreground text-xs">
                {t('audio_selector.selected_scope', { count: selectedCardCount })}
              </span>
            </div>
          )}

          {/* Nhóm Tiếng Nhật */}
          <div className="space-y-2">
            <div className="flex items-center justify-between px-0.5">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                {t('audio_selector.japanese_group')}
              </span>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              {/* Option 1: Web VoiceVox */}
              <button
                type="button"
                onClick={onSelectWebVoiceVox}
                className="flex items-start justify-between p-3 rounded-xl border border-border/60 bg-card hover:bg-primary/5 hover:border-primary/40 active:scale-[0.99] transition-all duration-200 text-left group shadow-2xs cursor-pointer"
              >
                <div className="flex items-start gap-2.5 min-w-0 pr-1">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0 group-hover:scale-105 transition-transform mt-0.5">
                    <Cloud className="size-4" />
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <div className="text-xs font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5">
                      <span>{t('audio_selector.web_voicevox')}</span>
                    </div>
                    <div className="text-[11px] text-muted-foreground line-clamp-2">
                      {t('audio_selector.cloud_api_desc', {
                        voice: webTtsSettings.character
                          ? t('audio_selector.voice_number', { id: webTtsSettings.character })
                          : t('audio_selector.default_voice'),
                      })}
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1.5 py-0 font-semibold bg-primary/10 text-primary border-primary/20 rounded-md"
                  >
                    {t('audio_selector.cloud_badge')}
                  </Badge>
                  <ChevronRight className="size-3.5 text-muted-foreground/60 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </div>
              </button>

              {/* Option 2: VoiceVox Local */}
              <button
                type="button"
                onClick={() => onSelectLocalVoice('voicevox', targetVoicevoxId)}
                className="flex items-start justify-between p-3 rounded-xl border border-border/60 bg-card hover:bg-primary/5 hover:border-primary/40 active:scale-[0.99] transition-all duration-200 text-left group shadow-2xs cursor-pointer"
              >
                <div className="flex items-start gap-2.5 min-w-0 pr-1">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 shrink-0 group-hover:scale-105 transition-transform mt-0.5">
                    <Cpu className="size-4" />
                  </div>
                  <div className="space-y-0.5 min-w-0">
                    <div className="text-xs font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5">
                      <span>{t('audio_selector.voicevox_local')}</span>
                    </div>
                    <div className="text-[11px] text-muted-foreground line-clamp-2">
                      {t('audio_selector.flama_audio_desc', { id: targetVoicevoxId })}
                    </div>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1.5 py-0 font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 rounded-md"
                  >
                    {t('audio_selector.local_badge')}
                  </Badge>
                  <ChevronRight className="size-3.5 text-muted-foreground/60 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </div>
              </button>
            </div>
          </div>

          {/* Nhóm Đa ngôn ngữ Kokoro */}
          <div className="space-y-2 pt-1">
            <div className="flex items-center justify-between px-0.5">
              <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
                <Globe className="size-3.5 text-primary" />
                <span>{t('audio_selector.offline_group')}</span>
              </div>
              <Badge
                variant="outline"
                className="text-[9px] px-1.5 py-0 font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 rounded-md"
              >
                {t('audio_selector.local_badge')}
              </Badge>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {KOKORO_VOICE_CONFIGS.map((item) => {
                const activeVoiceId = localSettings.lastVoiceIdKokoroByLang?.[item.lang] || item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectLocalVoice('kokoro', activeVoiceId)}
                    className="flex items-center justify-between p-2.5 rounded-xl border border-border/60 bg-card hover:bg-primary/5 hover:border-primary/40 active:scale-[0.99] transition-all duration-200 text-left group shadow-2xs cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-1">
                      <div className="flex size-7 items-center justify-center rounded-lg bg-muted/60 text-sm shrink-0 group-hover:scale-105 transition-transform">
                        {item.flag}
                      </div>
                      <div className="space-y-0.5 min-w-0">
                        <div className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                          {t(`audio_selector.voices.${item.labelKey}`)}
                        </div>
                        <div className="text-[10px] text-muted-foreground font-mono truncate">
                          Kokoro · {activeVoiceId}
                        </div>
                      </div>
                    </div>
                    <ChevronRight className="size-3.5 text-muted-foreground/60 group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0 ml-1" />
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <DialogFooter className="px-4 sm:px-6 py-2.5 sm:py-3 border-t border-border/60 bg-muted/20 flex flex-row items-center justify-between gap-2 shrink-0">
          <span className="text-[11px] text-muted-foreground truncate">
            {t('audio_selector.footer_hint')}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs px-3 rounded-lg border-border/70 hover:bg-muted text-foreground font-medium shrink-0"
            onClick={onClose}
          >
            {t('audio_selector.close')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

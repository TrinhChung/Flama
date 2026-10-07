import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertTriangle,
  LoaderCircle,
  Play,
  Volume2,
} from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'
import { BrowseTtsVoiceSettings } from './BrowseTtsVoiceSettings'
import { BrowseTtsFieldMapping } from './BrowseTtsFieldMapping'

export interface BrowseTtsModalProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseTtsModal({ browse }: BrowseTtsModalProps) {
  const { t } = useTranslation('browse')
  const {
    isTtsModalOpen,
    setIsTtsModalOpen,
    ttsVoicesQuery,
    ttsApiKey,
    setTtsApiKey,
    showApiKey,
    setShowApiKey,
    isKeySaved,
    isSavingKey,
    saveApiKeyIfValid,
    ttsCharacter,
    setTtsCharacter,
    ttsSourceField,
    setTtsSourceField,
    ttsDestinationField,
    setTtsDestinationField,
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
    handlePreviewVoiceVox,
    handleResetTtsDefaults,
    generateTtsMutation,
    targetTtsCardIds,
    selectedCards,
    selectedDeckId,
    selectedDeck,
    cards,
    isPreviewing,
    availableSourceFieldNames,
    availableAudioFieldNames,
  } = browse

  const availableVoices = ttsVoicesQuery.data?.items || []

  const isDeckScope = selectedCards.length === 0 && Boolean(selectedDeckId)
  const isMixedNoteTypes = isDeckScope && Boolean(selectedDeck?.has_mixed_note_types)
  const deckCardCount = selectedDeck?.counts?.total ?? cards.length
  const effectiveCardCount = isDeckScope ? deckCardCount : targetTtsCardIds.length

  const handleGenerate = () => {
    generateTtsMutation.mutate({
      card_ids: isDeckScope ? undefined : targetTtsCardIds,
      deck_id: isDeckScope && selectedDeckId ? selectedDeckId : undefined,
      source_field: ttsSourceField,
      destination_field: ttsDestinationField,
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

  return (
    <Dialog open={isTtsModalOpen} onOpenChange={setIsTtsModalOpen}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-xl sm:rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-4 sm:px-6 py-3.5 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <Volume2 className="size-4.5 sm:size-5 text-primary shrink-0" />
            <span>{t('tts_modal.title')}</span>
          </DialogTitle>
          <DialogDescription className="text-xs mt-1 text-muted-foreground">
            {t('tts_modal.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-4 space-y-4 text-xs min-h-0">
          {/* Target Cards Selection Count banner */}
          <div className="p-3 bg-muted/40 border border-border/60 rounded-xl flex items-center justify-between shadow-3xs">
            <span className="font-semibold text-foreground">
              {t('tts_modal.scope_label')}{' '}
              <strong className="text-primary font-bold ml-1">
                {isDeckScope
                  ? t('tts_modal.entire_deck_scope', {
                      name: selectedDeck?.name || 'này',
                      count: deckCardCount,
                    })
                  : t('tts_modal.selected_cards_scope', {
                      count: targetTtsCardIds.length,
                    })}
              </strong>
            </span>
            <Badge variant="outline" className="text-[10px] bg-primary/5 text-primary border-primary/20 font-bold px-2.5 py-0.5 rounded-full shrink-0">
              {t('tts_modal.deck_badge', {
                count: effectiveCardCount,
                isDeck: isDeckScope ? '(Cả deck)' : '',
              })}
            </Badge>
          </div>

          {/* Mixed Note Types Warning Banner */}
          {isMixedNoteTypes && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl flex items-start gap-2.5 text-amber-800 dark:text-amber-200">
              <AlertTriangle className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs space-y-0.5">
                <p className="font-bold">
                  {t('tts_modal.mixed_types_title')}
                </p>
                <p className="text-[11px] text-amber-700/90 dark:text-amber-300/90">
                  {selectedDeck?.note_type_names?.length
                    ? `${t('tts_modal.mixed_types_detected', { types: selectedDeck.note_type_names.join(', ') })} `
                    : ''}
                  {t('tts_modal.mixed_types_desc')}
                </p>
              </div>
            </div>
          )}

          <BrowseTtsFieldMapping
            ttsApiKey={ttsApiKey}
            setTtsApiKey={setTtsApiKey}
            showApiKey={showApiKey}
            setShowApiKey={setShowApiKey}
            isKeySaved={isKeySaved}
            isSavingKey={isSavingKey}
            saveApiKeyIfValid={saveApiKeyIfValid}
            ttsCharacter={ttsCharacter}
            setTtsCharacter={setTtsCharacter}
            ttsVoicesPending={ttsVoicesQuery.isPending}
            availableVoices={availableVoices}
            ttsSourceField={ttsSourceField}
            setTtsSourceField={setTtsSourceField}
            availableSourceFieldNames={availableSourceFieldNames}
            ttsDestinationField={ttsDestinationField}
            setTtsDestinationField={setTtsDestinationField}
            availableAudioFieldNames={availableAudioFieldNames}
          />

          <BrowseTtsVoiceSettings
            ttsVolumeScale={ttsVolumeScale}
            setTtsVolumeScale={setTtsVolumeScale}
            ttsPitch={ttsPitch}
            setTtsPitch={setTtsPitch}
            ttsSpeed={ttsSpeed}
            setTtsSpeed={setTtsSpeed}
            ttsIntonationScale={ttsIntonationScale}
            setTtsIntonationScale={setTtsIntonationScale}
            ttsInitialSilence={ttsInitialSilence}
            setTtsInitialSilence={setTtsInitialSilence}
            ttsFinalSilence={ttsFinalSilence}
            setTtsFinalSilence={setTtsFinalSilence}
            ttsAppendAudio={ttsAppendAudio}
            setTtsAppendAudio={setTtsAppendAudio}
            ttsUseOpus={ttsUseOpus}
            setTtsUseOpus={setTtsUseOpus}
            handleResetTtsDefaults={handleResetTtsDefaults}
          />
        </div>

        <DialogFooter className="px-4 sm:px-6 py-4 border-t bg-muted/20 flex items-center justify-between gap-3 shrink-0">
          <Button variant="outline" size="sm" onClick={() => setIsTtsModalOpen(false)}>
            {t('tts_modal.close')}
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handlePreviewVoiceVox}
              disabled={isPreviewing || generateTtsMutation.isPending}
            >
              {isPreviewing ? <LoaderCircle className="size-3.5 mr-1 animate-spin" /> : <Play className="size-3.5 mr-1" />}
              {t('tts_modal.preview_btn')}
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={handleGenerate}
              disabled={
                generateTtsMutation.isPending
                || isMixedNoteTypes
                || effectiveCardCount === 0
                || availableSourceFieldNames.length === 0
                || availableAudioFieldNames.length === 0
                || !ttsSourceField
                || !ttsDestinationField
              }
            >
              {generateTtsMutation.isPending ? <LoaderCircle className="size-3.5 mr-1 animate-spin" /> : null}
              {t('tts_modal.start_btn', { count: effectiveCardCount })}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

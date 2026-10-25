import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import {
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from '@/components/ui/dropdown-menu'
import type { useBrowseState } from '../hooks/useBrowseState'

export interface BrowseAudioDropdownMenuProps {
  setIsTtsModalOpen: (val: boolean) => void
  setLocalAudioEngineId: (engine: 'voicevox' | 'kokoro') => void
  setLocalAudioDefaultVoiceId: (voice: string | undefined) => void
  setLocalAudioTargetCardIds: (cards: string[]) => void
  setIsLocalAudioModalOpen: (val: boolean) => void
  selectedCards: string[]
  selectedDeckId?: number | null
  selectedDeck?: ReturnType<typeof useBrowseState>['selectedDeck']
}

export function BrowseAudioDropdownMenu({
  setIsTtsModalOpen,
  setLocalAudioEngineId,
  setLocalAudioDefaultVoiceId,
  setLocalAudioTargetCardIds,
  setIsLocalAudioModalOpen,
  selectedCards,
  selectedDeckId,
  selectedDeck,
}: BrowseAudioDropdownMenuProps) {
  const { t } = useTranslation('browse')

  const handleSelectWebVoiceVox = () => {
    if (selectedCards.length === 0) {
      if (!selectedDeckId) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (!selectedDeck || selectedDeck.summary_loaded === false) return
      if (selectedDeck.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    setIsTtsModalOpen(true)
  }

  const handleSelectLocalVoice = (engine: 'voicevox' | 'kokoro', voice: string | undefined) => {
    if (selectedCards.length === 0) {
      if (!selectedDeckId) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (!selectedDeck || selectedDeck.summary_loaded === false) return
      if (selectedDeck.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    setLocalAudioEngineId(engine)
    setLocalAudioDefaultVoiceId(voice)
    setLocalAudioTargetCardIds(selectedCards)
    setIsLocalAudioModalOpen(true)
  }

  return (
    <>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          <span className="font-medium">{t('audio_menu.japanese')}</span>
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="w-48">
          <DropdownMenuItem onClick={handleSelectWebVoiceVox} disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}>
            <span className="font-medium text-foreground">{t('audio_menu.web_voicevox')}</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
            onClick={() => handleSelectLocalVoice('voicevox', '3')}
            className="flex items-center justify-between font-medium cursor-pointer"
          >
            <span>{t('audio_menu.local_voicevox')}</span>
            <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
              {t('audio_menu.local_badge')}
            </Badge>
          </DropdownMenuItem>
        </DropdownMenuSubContent>
      </DropdownMenuSub>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'af_bella')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.english')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'zf_xiaobei')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.chinese')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'ef_dora')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.spanish')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'ff_siwis')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.french')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'if_sara')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.italian')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        disabled={selectedCards.length === 0 && (!selectedDeck || selectedDeck.summary_loaded === false)}
        onClick={() => handleSelectLocalVoice('kokoro', 'pf_dora')}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>{t('audio_menu.portuguese')}</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          {t('audio_menu.local_badge')}
        </Badge>
      </DropdownMenuItem>
    </>
  )
}

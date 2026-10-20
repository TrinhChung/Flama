import '@/shared/config/i18n'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  HelpCircle,
  MoreHorizontal,
  PenTool,
  Printer,
  Volume2,
} from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { LocalAudioDialog } from '@/features/audio/components/LocalAudioDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Brand } from '@/shared/components/Brand'
import { useBrowseState } from '../hooks/useBrowseState'
import { BrowseDeckSidebar } from '../components/BrowseDeckSidebar'
import { BrowseToolbar } from '../components/BrowseToolbar'
import { BrowseCardTable } from '../components/BrowseCardTable'
import { BrowseCardEditor } from '../components/BrowseCardEditor'
import { BrowseTtsModal } from '../components/BrowseTtsModal'
import { BrowseStrokeModal } from '../components/BrowseStrokeModal'
import { BrowseAudioSelectorModal } from '../components/BrowseAudioSelectorModal'
import { BrowseAudioDropdownMenu } from '../components/BrowseAudioDropdownMenu'
import { BrowseMobileTabBar } from '../components/BrowseMobileTabBar'
import { LazyDeckWorksheetModal } from '@/features/worksheets/components/LazyDeckWorksheetModal'
import { ContextHelpButton } from '@/features/guide/components/ContextHelpButton'

export function BrowsePage() {
  const { t } = useTranslation('browse')
  const navigate = useNavigate()
  const browse = useBrowseState()
  const [isAudioSelectorOpen, setIsAudioSelectorOpen] = useState(false)

  const {
    urlDeckId,
    audioPlayerRef,
    setIsTtsModalOpen,
    isLocalAudioModalOpen,
    setIsLocalAudioModalOpen,
    localAudioEngineId,
    setLocalAudioEngineId,
    localAudioDefaultVoiceId,
    setLocalAudioDefaultVoiceId,
    localAudioTargetCardIds,
    setLocalAudioTargetCardIds,
    selectedCards,
    activeCardId,
    availableSourceFieldNames,
    availableAudioFieldNames,
    mobileTab,
    setMobileTab,
  } = browse

  const openWorksheetModal = () => {
    if (selectedCards.length === 0) {
      if (!browse.selectedDeckId && !browse.cardsQuery.data?.items[0]?.deck_id) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (browse.selectedDeck?.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    const firstDeckId = browse.cardsQuery.data?.items[0]?.deck_id
    const targetDeckId = browse.selectedDeckId || firstDeckId || 1
    browse.setWorksheetTargetDeckId(targetDeckId)
    browse.setWorksheetTargetCardIds(selectedCards.length > 0 ? selectedCards : undefined)
    browse.setIsWorksheetModalOpen(true)
  }

  const openBatchStrokeModal = () => {
    if (selectedCards.length === 0) {
      if (!browse.selectedDeckId) {
        toast.info(t('toasts.deck_or_cards_required'))
        return
      }
      if (browse.selectedDeck?.has_mixed_note_types) {
        toast.error(t('toasts.mixed_note_types_error'))
        return
      }
    }
    browse.setStrokeModalMode('batch')
    browse.setIsStrokeModalOpen(true)
  }

  const worksheetTitle = selectedCards.length === 0
    ? browse.selectedDeck
      ? t('header.worksheet_deck_tooltip', {
          name: browse.selectedDeck.name,
          count: browse.selectedDeck.counts?.total ?? 0,
        })
      : t('header.worksheet_generic_tooltip')
    : t('header.worksheet_selected_tooltip', { count: selectedCards.length })

  const strokeTitle = selectedCards.length === 0 && browse.selectedDeck
    ? t('header.svg_stroke_deck_tooltip', {
        name: browse.selectedDeck.name,
        count: browse.selectedDeck.counts?.total ?? 0,
      })
    : undefined

  return (
    <div className="flex flex-col h-screen h-[100dvh] w-full overflow-hidden bg-background text-foreground">
      {/* Hidden Audio Player for Preview */}
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Top Navbar Header for Fullscreen Browse */}
      <header className="sticky top-0 z-30 flex h-12 sm:h-14 shrink-0 items-center justify-between border-b border-border/60 bg-background/95 px-2.5 sm:px-4 backdrop-blur-md">
        <div className="flex items-center gap-1.5 sm:gap-2.5 min-w-0">
          <Brand compact size="sm" hideTextOnCollapse />

          {urlDeckId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 sm:h-8 text-[11px] sm:text-xs font-bold text-primary border-primary/30 hover:bg-primary/10 bg-background rounded-full gap-1.5 px-2 sm:px-3 shrink-0"
              onClick={() => navigate(`/study?deck_id=${urlDeckId}`)}
              title={t('header.back_to_study')}
            >
              <ArrowLeft className="size-3.5" />
              <span className="hidden sm:inline">{t('header.back_to_study')}</span>
              <span className="sm:hidden">{t('header.study_short')}</span>
            </Button>
          ) : null}

          <span className="hidden md:inline text-xs sm:text-sm font-semibold text-foreground truncate">
            {t('header.browse_cards')}
          </span>
        </div>

        {/* Desktop Header Actions (sm and above) */}
        <div className="hidden sm:flex items-center gap-1 sm:gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1.5 bg-background hover:bg-muted border-border"
            onClick={openWorksheetModal}
            title={worksheetTitle}
          >
            <Printer className="size-3.5 text-primary" />
            <span>{t('header.worksheet')}</span>
            {selectedCards.length > 0 ? (
              <Badge
                variant="secondary"
                className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-bold bg-primary/15 text-primary rounded-full"
              >
                {selectedCards.length}
              </Badge>
            ) : browse.selectedDeck ? (
              <Badge
                variant="secondary"
                className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-medium bg-muted text-muted-foreground rounded-full"
              >
                {browse.selectedDeck.counts?.total ?? 0}
              </Badge>
            ) : null}
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 bg-background hover:bg-muted border-border"
            onClick={openBatchStrokeModal}
            title={strokeTitle}
          >
            <PenTool className="size-3.5 text-primary" />
            <span>{t('header.svg_stroke')}</span>
            {selectedCards.length === 0 && browse.selectedDeck ? (
              <Badge
                variant="secondary"
                className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-medium bg-muted text-muted-foreground rounded-full"
              >
                {browse.selectedDeck.counts?.total ?? 0}
              </Badge>
            ) : null}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 bg-background hover:bg-muted border-border"
              >
                <Volume2 className="size-3.5 text-primary" />
                <span>{t('header.audio')}</span>
                <ChevronDown className="size-3 opacity-60 ml-0.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <BrowseAudioDropdownMenu
                setIsTtsModalOpen={setIsTtsModalOpen}
                setLocalAudioEngineId={setLocalAudioEngineId}
                setLocalAudioDefaultVoiceId={setLocalAudioDefaultVoiceId}
                setLocalAudioTargetCardIds={setLocalAudioTargetCardIds}
                setIsLocalAudioModalOpen={setIsLocalAudioModalOpen}
                selectedCards={selectedCards}
                selectedDeckId={browse.selectedDeckId}
                selectedDeck={browse.selectedDeck}
              />
            </DropdownMenuContent>
          </DropdownMenu>

          <ContextHelpButton
            guidePath="/guide/browse/search-syntax"
            guideTitle={t('header.help_search_tips')}
            troubleshootPath="/guide/troubleshooting/dashboard-study"
            troubleshootTitle={t('header.help_troubleshoot')}
            label={t('header.help')}
            variant="outline"
            size="xs"
          />
        </div>

        {/* Mobile Consolidated Action Menu (< sm) */}
        <div className="flex sm:hidden items-center shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 rounded-full text-xs px-2.5 gap-1.5 bg-background hover:bg-muted border-border font-medium shrink-0"
                aria-label={t('header.actions_menu')}
              >
                <MoreHorizontal className="size-4 text-foreground" />
                <span>{t('header.actions')}</span>
                {selectedCards.length > 0 ? (
                  <Badge
                    variant="secondary"
                    className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-bold bg-primary/15 text-primary rounded-full"
                  >
                    {selectedCards.length}
                  </Badge>
                ) : browse.selectedDeck ? (
                  <Badge
                    variant="secondary"
                    className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-medium bg-muted text-muted-foreground rounded-full"
                  >
                    {browse.selectedDeck.counts?.total ?? 0}
                  </Badge>
                ) : null}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 p-1.5 rounded-xl shadow-lg border-border/80">
              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                {t('header.tools_section')}
              </DropdownMenuLabel>

              <DropdownMenuItem
                onClick={openWorksheetModal}
                className="flex items-center justify-between cursor-pointer py-2"
              >
                <div className="flex items-center gap-2">
                  <Printer className="size-4 text-primary" />
                  <span className="text-xs font-medium">{t('header.worksheet')}</span>
                </div>
                {selectedCards.length > 0 ? (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-bold bg-primary/15 text-primary rounded-full">
                    {selectedCards.length}
                  </Badge>
                ) : browse.selectedDeck ? (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-medium bg-muted text-muted-foreground rounded-full">
                    {browse.selectedDeck.counts?.total ?? 0}
                  </Badge>
                ) : null}
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={openBatchStrokeModal}
                className="flex items-center gap-2 cursor-pointer py-2"
              >
                <PenTool className="size-4 text-primary" />
                <span className="text-xs font-medium">{t('header.svg_stroke')}</span>
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={() => {
                  if (selectedCards.length === 0) {
                    if (!browse.selectedDeckId) {
                      toast.info(t('toasts.deck_or_cards_required'))
                      return
                    }
                    if (browse.selectedDeck?.has_mixed_note_types) {
                      toast.error(t('toasts.mixed_note_types_error'))
                      return
                    }
                  }
                  setIsAudioSelectorOpen(true)
                }}
                className="flex items-center gap-2 cursor-pointer py-2"
              >
                <Volume2 className="size-4 text-primary" />
                <span className="text-xs font-medium">{t('header.audio')}</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator className="my-1" />

              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                {t('header.help_section')}
              </DropdownMenuLabel>
              <DropdownMenuItem asChild className="cursor-pointer py-1.5">
                <Link to="/guide/browse/search-syntax" className="flex items-center gap-2 text-xs">
                  <BookOpen className="size-3.5 text-primary" />
                  <span>{t('header.help_search_tips')}</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild className="cursor-pointer py-1.5">
                <Link to="/guide/troubleshooting/dashboard-study" className="flex items-center gap-2 text-xs">
                  <HelpCircle className="size-3.5 text-amber-500" />
                  <span>{t('header.help_troubleshoot')}</span>
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Main Workspace layout */}
      <div className="flex-1 flex overflow-hidden min-h-0 w-full relative">
        {/* Left Side: Deck Sidebar */}
        <div className={`${mobileTab === 'decks' ? 'flex' : 'hidden md:flex'} h-full shrink-0 w-full md:w-auto`}>
          <BrowseDeckSidebar browse={browse} />
        </div>

        {/* Center Side: Cards Table & Paging */}
        <div className={`flex-1 flex flex-col overflow-hidden h-full ${mobileTab === 'cards' ? 'flex' : 'hidden md:flex'}`}>
          <BrowseToolbar browse={browse} />
          <BrowseCardTable
            cards={browse.cards}
            isPending={browse.cardsQuery.isPending}
            isShowingPreviousResult={browse.cardsQuery.isPlaceholderData}
            error={browse.cardsQuery.isError && !browse.cardsQuery.data ? browse.cardsQuery.error : null}
            onRetry={browse.refetchCards}
            total={browse.cardsQuery.data?.total || 0}
            pages={browse.cardsQuery.data?.pages || 1}
            page={browse.page}
            setPage={browse.setPage}
            perPage={browse.perPage}
            onPerPageChange={browse.handlePerPageChange}
            selectedCardSet={browse.selectedCardSet}
            selectedCount={selectedCards.length}
            allSelected={browse.allSelected}
            onToggleSelectAll={browse.handleToggleSelectAllCards}
            onToggleCardSelected={browse.handleToggleCardSelected}
            activeCardId={activeCardId}
            onActivateCard={browse.handleActivateCard}
            sortBy={browse.sortBy}
            sortDir={browse.sortDir}
            onSortChange={browse.handleSortChange}
            arrayViewMode={browse.arrayViewMode}
          />
        </div>

        {/* Right Side: Active Card Editor */}
        <BrowseCardEditor browse={browse} />
      </div>

      {/* Mobile Tab Swapping Bar (< lg screens) */}
      <BrowseMobileTabBar
        mobileTab={mobileTab}
        setMobileTab={setMobileTab}
        activeCardId={activeCardId}
      />

      {/* Mobile Audio Voice/Engine Selection Modal Dialog */}
      <BrowseAudioSelectorModal
        isOpen={isAudioSelectorOpen}
        onClose={() => setIsAudioSelectorOpen(false)}
        selectedCardCount={selectedCards.length}
        onSelectWebVoiceVox={() => {
          setIsAudioSelectorOpen(false)
          setIsTtsModalOpen(true)
        }}
        onSelectLocalVoice={(engineId, voiceId) => {
          setIsAudioSelectorOpen(false)
          setLocalAudioEngineId(engineId)
          setLocalAudioDefaultVoiceId(voiceId)
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
      />

      {/* VoiceVox TTS Generation Modal Dialog popup */}
      <BrowseTtsModal browse={browse} />

      {/* Kanji/Hanzi Stroke Diagram Generation Modal */}
      <BrowseStrokeModal
        browse={browse}
        isOpen={browse.isStrokeModalOpen}
        onClose={() => browse.setIsStrokeModalOpen(false)}
        mode={browse.strokeModalMode}
        cardId={browse.strokeModalCardId}
      />

      {/* Printable Worksheet Generator Modal */}
      {browse.isWorksheetModalOpen && (
        <LazyDeckWorksheetModal
          open={browse.isWorksheetModalOpen}
          onOpenChange={browse.setIsWorksheetModalOpen}
          deckId={browse.worksheetTargetDeckId || browse.selectedDeckId || 1}
          initialCardIds={browse.worksheetTargetCardIds}
        />
      )}

      {/* Local Offline TTS Audio Generation modal */}
      {isLocalAudioModalOpen && (
        <LocalAudioDialog
          isOpen={isLocalAudioModalOpen}
          onClose={() => setIsLocalAudioModalOpen(false)}
          selectedCardIds={localAudioTargetCardIds}
          activeCardId={activeCardId}
          deckId={browse.selectedDeckId || undefined}
          deckName={browse.selectedDeck?.name}
          availableFieldNames={availableSourceFieldNames}
          availableAudioFieldNames={availableAudioFieldNames}
          engineId={localAudioEngineId}
          defaultVoiceId={localAudioDefaultVoiceId}
          onSuccess={() => {
            // refresh cards list
            void browse.cardsQuery.refetch()
            if (activeCardId) {
              void browse.cardDetailQuery.refetch()
            }
          }}
        />
      )}
    </div>
  )
}

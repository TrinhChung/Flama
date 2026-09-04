import { useState } from 'react'
import {
  ArrowLeft,
  BookOpen,
  ChevronDown,
  HelpCircle,
  Layers,
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
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Brand } from '@/shared/components/Brand'

interface AudioDropdownMenuItemsProps {
  setIsTtsModalOpen: (val: boolean) => void
  setLocalAudioEngineId: (engine: 'voicevox' | 'kokoro') => void
  setLocalAudioDefaultVoiceId: (voice: string | undefined) => void
  setLocalAudioTargetCardIds: (cards: string[]) => void
  setIsLocalAudioModalOpen: (val: boolean) => void
  selectedCards: string[]
}

function AudioDropdownMenuItems({
  setIsTtsModalOpen,
  setLocalAudioEngineId,
  setLocalAudioDefaultVoiceId,
  setLocalAudioTargetCardIds,
  setIsLocalAudioModalOpen,
  selectedCards,
}: AudioDropdownMenuItemsProps) {
  return (
    <>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          <span className="font-medium">🇯🇵 Tiếng Nhật</span>
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="w-48">
          <DropdownMenuItem onClick={() => setIsTtsModalOpen(true)}>
            <span className="font-medium text-foreground">Web VoiceVox</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() => {
              setLocalAudioEngineId('voicevox')
              setLocalAudioDefaultVoiceId('3')
              setLocalAudioTargetCardIds(selectedCards)
              setIsLocalAudioModalOpen(true)
            }}
            className="flex items-center justify-between font-medium cursor-pointer"
          >
            <span>VoiceVox Local</span>
            <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
              Local
            </Badge>
          </DropdownMenuItem>
        </DropdownMenuSubContent>
      </DropdownMenuSub>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('af_bella')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇺🇸/🇬🇧 Tiếng Anh Local</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('zf_xiaobei')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇨🇳 Tiếng Trung Local</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('ef_dora')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇪🇸 Tiếng Tây Ban Nha</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('ff_siwis')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇫🇷 Tiếng Pháp Local</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('if_sara')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇮🇹 Tiếng Ý Local</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>

      <DropdownMenuItem
        onClick={() => {
          setLocalAudioEngineId('kokoro')
          setLocalAudioDefaultVoiceId('pf_dora')
          setLocalAudioTargetCardIds(selectedCards)
          setIsLocalAudioModalOpen(true)
        }}
        className="flex items-center justify-between font-medium cursor-pointer"
      >
        <span>🇧🇷 Tiếng Bồ Đào Nha</span>
        <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
          Local
        </Badge>
      </DropdownMenuItem>
    </>
  )
}

import { useBrowseState } from '../hooks/useBrowseState'
import { BrowseDeckSidebar } from '../components/BrowseDeckSidebar'
import { BrowseToolbar } from '../components/BrowseToolbar'
import { BrowseCardTable } from '../components/BrowseCardTable'
import { BrowseCardEditor } from '../components/BrowseCardEditor'
import { BrowseTtsModal } from '../components/BrowseTtsModal'
import { BrowseStrokeModal } from '../components/BrowseStrokeModal'
import { BrowseAudioSelectorModal } from '../components/BrowseAudioSelectorModal'
import { DeckWorksheetModal } from '@/features/worksheets'
import { ContextHelpButton } from '@/features/guide'

export function BrowsePage() {
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
    const firstDeckId = browse.cardsQuery.data?.items[0]?.deck_id
    const targetDeckId = browse.selectedDeckId || firstDeckId || 1
    browse.setWorksheetTargetDeckId(targetDeckId)
    browse.setWorksheetTargetCardIds(selectedCards.length > 0 ? selectedCards : undefined)
    browse.setIsWorksheetModalOpen(true)
  }

  const openBatchStrokeModal = () => {
    browse.setStrokeModalMode('batch')
    browse.setIsStrokeModalOpen(true)
  }

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
              title="Quay lại bài học"
            >
              <ArrowLeft className="size-3.5" />
              <span className="hidden sm:inline">Quay lại bài học</span>
              <span className="sm:hidden">Bài học</span>
            </Button>
          ) : null}

          <span className="hidden md:inline text-xs sm:text-sm font-semibold text-foreground truncate">
            Duyệt thẻ
          </span>
        </div>

        {/* Desktop Header Actions (sm and above) */}
        <div className="hidden sm:flex items-center gap-1 sm:gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1.5 bg-background hover:bg-muted border-border"
            onClick={openWorksheetModal}
            title={
              selectedCards.length === 0
                ? 'In bài tập hoặc tạo trang trắng luyện viết cho bộ thẻ này'
                : `In bài tập cho ${selectedCards.length} thẻ đã chọn`
            }
          >
            <Printer className="size-3.5 text-primary" />
            <span>In bài tập</span>
            {selectedCards.length > 0 && (
              <Badge
                variant="secondary"
                className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-bold bg-primary/15 text-primary rounded-full"
              >
                {selectedCards.length}
              </Badge>
            )}
          </Button>

          <Button
            variant="outline"
            size="sm"
            className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 bg-background hover:bg-muted border-border"
            onClick={openBatchStrokeModal}
          >
            <PenTool className="size-3.5 text-primary" />
            <span>Tạo nét SVG</span>
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 bg-background hover:bg-muted border-border"
              >
                <Volume2 className="size-3.5 text-primary" />
                <span>Tạo âm thanh</span>
                <ChevronDown className="size-3 opacity-60 ml-0.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <AudioDropdownMenuItems
                setIsTtsModalOpen={setIsTtsModalOpen}
                setLocalAudioEngineId={setLocalAudioEngineId}
                setLocalAudioDefaultVoiceId={setLocalAudioDefaultVoiceId}
                setLocalAudioTargetCardIds={setLocalAudioTargetCardIds}
                setIsLocalAudioModalOpen={setIsLocalAudioModalOpen}
                selectedCards={selectedCards}
              />
            </DropdownMenuContent>
          </DropdownMenu>

          <ContextHelpButton
            guidePath="/guide/browse/search-syntax"
            guideTitle="Mẹo tìm kiếm & Lọc thẻ"
            troubleshootPath="/guide/troubleshooting/dashboard-study"
            troubleshootTitle="Thẻ không hiển thị đúng?"
            label="Trợ giúp"
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
                aria-label="Menu tác vụ"
              >
                <MoreHorizontal className="size-4 text-foreground" />
                <span>Tác vụ</span>
                {selectedCards.length > 0 && (
                  <Badge
                    variant="secondary"
                    className="text-[10px] px-1.5 py-0 h-4 min-w-4 flex items-center justify-center font-bold bg-primary/15 text-primary rounded-full"
                  >
                    {selectedCards.length}
                  </Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56 p-1.5 rounded-xl shadow-lg border-border/80">
              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                Công cụ & Tiện ích
              </DropdownMenuLabel>

              <DropdownMenuItem
                onClick={openWorksheetModal}
                className="flex items-center justify-between cursor-pointer py-2"
              >
                <div className="flex items-center gap-2">
                  <Printer className="size-4 text-primary" />
                  <span className="text-xs font-medium">In bài tập</span>
                </div>
                {selectedCards.length > 0 && (
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-bold bg-primary/15 text-primary rounded-full">
                    {selectedCards.length}
                  </Badge>
                )}
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={openBatchStrokeModal}
                className="flex items-center gap-2 cursor-pointer py-2"
              >
                <PenTool className="size-4 text-primary" />
                <span className="text-xs font-medium">Tạo nét SVG</span>
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={() => setIsAudioSelectorOpen(true)}
                className="flex items-center gap-2 cursor-pointer py-2"
              >
                <Volume2 className="size-4 text-primary" />
                <span className="text-xs font-medium">Tạo âm thanh</span>
              </DropdownMenuItem>

              <DropdownMenuSeparator className="my-1" />

              <DropdownMenuLabel className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground px-2 py-1">
                Trợ giúp & Mẹo
              </DropdownMenuLabel>
              <DropdownMenuItem asChild className="cursor-pointer py-1.5">
                <Link to="/guide/browse/search-syntax" className="flex items-center gap-2 text-xs">
                  <BookOpen className="size-3.5 text-primary" />
                  <span>Mẹo tìm kiếm & Lọc thẻ</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild className="cursor-pointer py-1.5">
                <Link to="/guide/troubleshooting/dashboard-study" className="flex items-center gap-2 text-xs">
                  <HelpCircle className="size-3.5 text-amber-500" />
                  <span>Thẻ không hiển thị đúng?</span>
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
          <BrowseCardTable browse={browse} />
        </div>

        {/* Right Side: Active Card Editor */}
        <BrowseCardEditor browse={browse} />
      </div>

      {/* Mobile Tab Swapping Bar (< lg screens) */}
      <div className="lg:hidden shrink-0 h-12 border-t border-border/60 bg-background/95 flex items-center justify-around z-20 sticky bottom-0">
        <button
          type="button"
          onClick={() => setMobileTab('decks')}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
            mobileTab === 'decks' ? 'text-primary' : 'text-muted-foreground'
          }`}
        >
          <Layers className="size-4" />
          <span>Thư mục Decks</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('cards')}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
            mobileTab === 'cards' ? 'text-primary' : 'text-muted-foreground'
          }`}
        >
          <svg
            className="size-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect width="18" height="18" x="3" y="3" rx="2" />
            <path d="M3 9h18" />
            <path d="M9 21V9" />
          </svg>
          <span>Danh sách thẻ</span>
        </button>
        <button
          type="button"
          onClick={() => {
            if (activeCardId) {
              setMobileTab('editor')
            } else {
              toast.info('Vui lòng chọn 1 thẻ trước để sửa.')
            }
          }}
          className={`flex flex-col items-center justify-center flex-1 h-full text-[10px] font-bold gap-1 ${
            mobileTab === 'editor' ? 'text-primary' : 'text-muted-foreground'
          } ${!activeCardId ? 'opacity-40' : ''}`}
        >
          <svg
            className="size-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
          </svg>
          <span>Soạn thảo note</span>
        </button>
      </div>

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
        <DeckWorksheetModal
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

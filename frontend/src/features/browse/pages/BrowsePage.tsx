import {
  ArrowLeft,
  ChevronDown,
  Layers,
  Volume2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { LocalAudioDialog } from '@/features/audio/components/LocalAudioDialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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

export function BrowsePage() {
  const navigate = useNavigate()
  const browse = useBrowseState()

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
    availableFieldNames,
    mobileTab,
    setMobileTab,
  } = browse

  return (
    <div className="flex flex-col h-screen h-[100dvh] w-full overflow-hidden bg-background text-foreground">
      {/* Hidden Audio Player for Preview */}
      <audio ref={audioPlayerRef} className="hidden" />

      {/* Top Navbar Header for Fullscreen Browse */}
      <header className="sticky top-0 z-30 flex h-12 sm:h-14 shrink-0 items-center justify-between border-b border-border/60 bg-background/95 px-2.5 sm:px-4 backdrop-blur-md">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          {urlDeckId ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 text-xs font-bold text-primary border-primary/30 hover:bg-primary/10 bg-background rounded-full gap-1.5 px-3 shrink-0"
              onClick={() => navigate(`/study?deck_id=${urlDeckId}`)}
            >
              <ArrowLeft className="size-3.5" />
              <span>Quay lại bài học</span>
            </Button>
          ) : (
            <Brand compact size="sm" hideTextOnCollapse />
          )}
          <span className="hidden sm:inline text-xs sm:text-sm font-semibold text-foreground truncate">Duyệt thẻ</span>
        </div>

        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 sm:h-8 rounded-full text-[11px] sm:text-xs px-2 sm:px-3 gap-1 bg-background hover:bg-muted border-border"
              >
                <Volume2 className="size-3.5 text-primary" />
                <span className="hidden sm:inline">Tạo âm thanh</span>
                <ChevronDown className="size-3 opacity-60 ml-0.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
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
                    <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
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
                <Badge variant="outline" className="text-[10px] py-0 px-1 font-normal bg-emerald-50 text-emerald-700 border-emerald-300">
                  Local
                </Badge>
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

      {/* VoiceVox TTS Generation Modal Dialog popup */}
      <BrowseTtsModal browse={browse} />

      {/* Local Offline TTS Audio Generation modal */}
      {isLocalAudioModalOpen && (
        <LocalAudioDialog
          isOpen={isLocalAudioModalOpen}
          onClose={() => setIsLocalAudioModalOpen(false)}
          selectedCardIds={localAudioTargetCardIds}
          activeCardId={activeCardId}
          availableFieldNames={availableFieldNames}
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

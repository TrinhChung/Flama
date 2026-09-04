import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { ChevronRight, Volume2 } from 'lucide-react'

interface BrowseAudioSelectorModalProps {
  isOpen: boolean
  onClose: () => void
  onSelectWebVoiceVox: () => void
  onSelectLocalVoice: (engineId: 'voicevox' | 'kokoro', defaultVoiceId: string) => void
  selectedCardCount?: number
}

const KOKORO_VOICES = [
  { id: 'af_bella', label: '🇺🇸/🇬🇧 Tiếng Anh Local', desc: 'Kokoro English Voice' },
  { id: 'zf_xiaobei', label: '🇨🇳 Tiếng Trung Local', desc: 'Kokoro Chinese Voice' },
  { id: 'ef_dora', label: '🇪🇸 Tiếng Tây Ban Nha', desc: 'Kokoro Spanish Voice' },
  { id: 'ff_siwis', label: '🇫🇷 Tiếng Pháp Local', desc: 'Kokoro French Voice' },
  { id: 'if_sara', label: '🇮🇹 Tiếng Ý Local', desc: 'Kokoro Italian Voice' },
  { id: 'pf_dora', label: '🇧🇷 Tiếng Bồ Đào Nha', desc: 'Kokoro Portuguese Voice' },
]

export function BrowseAudioSelectorModal({
  isOpen,
  onClose,
  onSelectWebVoiceVox,
  onSelectLocalVoice,
  selectedCardCount = 0,
}: BrowseAudioSelectorModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[92vw] sm:max-w-md max-h-[85vh] flex flex-col p-0 rounded-2xl overflow-hidden border-border/70 shadow-2xl bg-card">
        <DialogHeader className="px-4 sm:px-6 py-3.5 sm:py-4 border-b bg-muted/20 shrink-0 text-left">
          <div className="flex items-center justify-between gap-2">
            <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
              <Volume2 className="size-4.5 sm:size-5 text-primary shrink-0" />
              <span>Tạo âm thanh phát âm</span>
            </DialogTitle>
            {selectedCardCount > 0 && (
              <Badge
                variant="secondary"
                className="text-[10px] px-2 py-0.5 font-bold bg-primary/15 text-primary rounded-full shrink-0"
              >
                {selectedCardCount} thẻ
              </Badge>
            )}
          </div>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Chọn công cụ và ngôn ngữ để tạo audio đọc cho thẻ học
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-4 text-xs">
          {/* Nhóm Tiếng Nhật */}
          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground px-1">
              🇯🇵 Tiếng Nhật
            </div>
            <div className="grid gap-2">
              <button
                type="button"
                onClick={onSelectWebVoiceVox}
                className="flex items-center justify-between p-3 rounded-xl border border-border/70 bg-background hover:bg-muted/60 transition text-left group"
              >
                <div className="space-y-0.5 min-w-0 pr-2">
                  <div className="text-xs font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5">
                    <span>Web VoiceVox</span>
                    <Badge variant="outline" className="text-[9px] px-1.5 py-0 font-medium">Cloud</Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground line-clamp-1">
                    Tạo âm thanh trực tuyến qua API đám mây
                  </div>
                </div>
                <ChevronRight className="size-4 text-muted-foreground shrink-0 group-hover:translate-x-0.5 transition-transform" />
              </button>

              <button
                type="button"
                onClick={() => onSelectLocalVoice('voicevox', '3')}
                className="flex items-center justify-between p-3 rounded-xl border border-border/70 bg-background hover:bg-muted/60 transition text-left group"
              >
                <div className="space-y-0.5 min-w-0 pr-2">
                  <div className="text-xs font-bold text-foreground group-hover:text-primary transition-colors flex items-center gap-1.5">
                    <span>VoiceVox Local</span>
                    <Badge
                      variant="outline"
                      className="text-[9px] px-1.5 py-0 font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30"
                    >
                      Offline
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground line-clamp-1">
                    Phát âm tiếng Nhật qua ứng dụng Flama Audio
                  </div>
                </div>
                <ChevronRight className="size-4 text-muted-foreground shrink-0 group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          </div>

          {/* Nhóm Đa ngôn ngữ Kokoro */}
          <div className="space-y-2">
            <div className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground px-1">
              🌐 Đa ngôn ngữ Offline (Kokoro Engine)
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {KOKORO_VOICES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelectLocalVoice('kokoro', item.id)}
                  className="flex items-center justify-between p-2.5 rounded-xl border border-border/70 bg-background hover:bg-muted/60 transition text-left group"
                >
                  <div className="space-y-0.5 min-w-0 pr-1">
                    <div className="text-xs font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                      {item.label}
                    </div>
                    <div className="text-[10px] text-muted-foreground truncate">{item.desc}</div>
                  </div>
                  <Badge
                    variant="outline"
                    className="text-[9px] px-1 py-0 font-normal bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 shrink-0"
                  >
                    Local
                  </Badge>
                </button>
              ))}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

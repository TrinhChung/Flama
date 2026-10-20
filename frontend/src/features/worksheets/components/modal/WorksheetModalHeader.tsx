import { Check, Eye, Loader2, Printer, Sliders, X, ZoomIn, ZoomOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import type { WizardStepId } from '../../config/wizardSteps'
import { getFitZoom, stepZoom } from '../../utils/zoom'

export type StudioMobileView = 'controls' | 'preview'

interface HeaderBaseProps {
  wizardStep: WizardStepId
  hasDeck: boolean
  deckLabel: string
  isGenerating: boolean
  onClose: () => void
}

export interface WorksheetDesktopHeaderProps extends HeaderBaseProps {
  totalNotes: number
  zoomLevel: number
  setZoomLevel: React.Dispatch<React.SetStateAction<number>>
  orientation?: 'portrait' | 'landscape'
  onPrint: () => void
  isPrinting: boolean
  canPrint: boolean
}

export function WorksheetDesktopHeader({
  wizardStep,
  hasDeck,
  deckLabel,
  isGenerating,
  onClose,
  totalNotes,
  zoomLevel,
  setZoomLevel,
  orientation,
  onPrint,
  isPrinting,
  canPrint,
}: WorksheetDesktopHeaderProps) {
  const { t } = useTranslation('worksheets')

  return (
    <DialogHeader className="hidden md:flex px-5 py-3 border-b border-border/80 bg-muted/40 shrink-0">
      <div className="flex items-center justify-between gap-4">
        {/* Left: Branding & Step / Deck Metadata */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="size-10 rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shadow-xs shrink-0">
            <Printer className="size-5" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <DialogTitle className="text-base font-bold text-foreground truncate">
                {wizardStep === 'deck'
                  ? t('modal.title_step_deck', 'Mẫu giấy luyện viết & In ấn (A4) - Chọn bộ thẻ')
                  : wizardStep === 'mapping'
                  ? t('modal.title_step_mapping', {
                      name: deckLabel,
                      defaultValue: `Ánh xạ trường dữ liệu - ${deckLabel}`,
                    })
                  : wizardStep === 'template'
                  ? t('modal.title_step_template', {
                      name: deckLabel,
                      defaultValue: `Chọn mẫu bài tập - ${deckLabel}`,
                    })
                  : hasDeck
                  ? t('modal.title_step_studio_deck', 'Xuất bài tập in ấn / PDF (A4)')
                  : t('modal.title_step_studio_standalone', 'Mẫu giấy luyện viết & In ấn (A4)')}
              </DialogTitle>
              <Badge variant="outline" className="text-[10px] font-semibold bg-primary/5 text-primary border-primary/20 shrink-0">
                {wizardStep === 'studio' ? t('modal.badge_studio', 'Live Studio') : t('modal.badge_wizard', 'Quy trình tạo')}
              </Badge>
            </div>
            <DialogDescription className="text-xs text-muted-foreground mt-0.5 flex items-center gap-2 truncate">
              {wizardStep === 'deck' ? (
                <span>{t('modal.desc_step_deck', 'Bước 1/4: Chọn bộ thẻ bạn muốn tạo mẫu giấy luyện viết & in ấn')}</span>
              ) : wizardStep === 'mapping' ? (
                <span>{t('modal.desc_step_mapping', 'Bước 2/4: Xác nhận các trường từ vựng, cách đọc, ý nghĩa')}</span>
              ) : wizardStep === 'template' ? (
                <span>{t('modal.desc_step_template', 'Bước 3/4: Chọn loại bài tập muốn in (Chữ Hán, Từ vựng, Đặt câu...)')}</span>
              ) : (
                <>
                  <span>{hasDeck ? deckLabel : t('modal.standalone_label', 'Mẫu giấy độc lập (Không cần deck)')}</span>
                  {hasDeck ? (
                    <>
                      <span>&bull;</span>
                      <span className="font-semibold text-foreground">
                        {t('modal.total_notes', { count: totalNotes, defaultValue: `${totalNotes} ghi chú` })}
                      </span>
                    </>
                  ) : (
                    <>
                      <span>&bull;</span>
                      <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                        {t('modal.free_practice', 'Tự do luyện viết')}
                      </span>
                    </>
                  )}
                  {isGenerating ? (
                    <span className="inline-flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium animate-pulse shrink-0">
                      <Loader2 className="size-3 animate-spin" />
                      <span>{t('modal.demo_updating', 'Đang cập nhật demo...')}</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium shrink-0">
                      <Check className="size-3" />
                      <span>{t('modal.demo_ready', 'Bản demo sẵn sàng')}</span>
                    </span>
                  )}
                </>
              )}
            </DialogDescription>
          </div>
        </div>

        {/* Center / Right: Controls, Zoom, Actions & Desktop Close Button */}
        <div className="flex items-center gap-2.5 shrink-0">
          {wizardStep === 'studio' && (
            <>
              {/* Zoom Controls */}
              <div className="flex items-center bg-background rounded-lg border border-border/80 px-1 py-0.5 shadow-2xs">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setZoomLevel((z) => stepZoom(z, -0.1))}
                  title={t('modal.zoom_out', 'Thu nhỏ')}
                >
                  <ZoomOut className="size-3.5" />
                </Button>
                <span className="text-xs font-bold px-2 min-w-12 text-center">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7"
                  onClick={() => setZoomLevel((z) => stepZoom(z, 0.1))}
                  title={t('modal.zoom_in', 'Phóng to')}
                >
                  <ZoomIn className="size-3.5" />
                </Button>
              </div>

              {/* Quick Zoom Presets */}
              <div className="hidden lg:flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoomLevel(getFitZoom(orientation))}
                  className="h-8 px-2.5 text-[11px] font-medium"
                >
                  {t('modal.zoom_fit', 'Vừa trang')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setZoomLevel(1)}
                  className="h-8 px-2.5 text-[11px] font-medium"
                >
                  100%
                </Button>
              </div>

              {/* Print Button */}
              <Button
                size="sm"
                onClick={onPrint}
                disabled={isPrinting || !canPrint}
                className="h-8.5 px-4 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md"
              >
                {isPrinting ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" />
                    <span>{t('modal.print_preparing', 'Đang chuẩn bị...')}</span>
                  </>
                ) : (
                  <>
                    <Printer className="size-3.5" />
                    <span>{t('modal.print_button', 'In / Lưu PDF')}</span>
                  </>
                )}
              </Button>
            </>
          )}

          {/* Desktop Close Button */}
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-lg text-muted-foreground hover:text-foreground ml-1"
            onClick={onClose}
            title={t('modal.close', 'Đóng')}
            aria-label={t('modal.close', 'Đóng')}
          >
            <X className="size-4" />
          </Button>
        </div>
      </div>
    </DialogHeader>
  )
}

export interface WorksheetMobileHeaderProps extends HeaderBaseProps {
  totalPages: number
  mobileView: StudioMobileView
  setMobileView: (view: StudioMobileView) => void
}

export function WorksheetMobileHeader({
  wizardStep,
  hasDeck,
  deckLabel,
  isGenerating,
  onClose,
  totalPages,
  mobileView,
  setMobileView,
}: WorksheetMobileHeaderProps) {
  const { t } = useTranslation('worksheets')

  return (
    <DialogHeader className="flex md:hidden px-3.5 py-2.5 border-b border-border/80 bg-muted/40 shrink-0 gap-2">
      {/* Row 1: Brand Icon + Title + Close Button */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="size-8 rounded-lg bg-orange-500/15 text-orange-600 dark:text-orange-400 flex items-center justify-center shrink-0">
            <Printer className="size-4" />
          </div>
          <div className="min-w-0">
            <DialogTitle className="text-sm font-bold text-foreground truncate">
              {wizardStep === 'deck'
                ? t('stepper.step_deck', 'Chọn bộ thẻ')
                : wizardStep === 'mapping'
                ? t('stepper.step_mapping', 'Ánh xạ dữ liệu')
                : wizardStep === 'template'
                ? t('stepper.step_template', 'Chọn mẫu bài tập')
                : hasDeck
                ? t('modal.title_step_studio_deck', 'Xuất bài tập in ấn / PDF (A4)')
                : t('modal.title_step_studio_standalone', 'Mẫu giấy luyện viết & In ấn (A4)')}
            </DialogTitle>
            <div className="text-[10px] text-muted-foreground truncate flex items-center gap-1.5">
              <span>{hasDeck ? deckLabel : 'Mẫu tự do'}</span>
              {wizardStep === 'studio' && (
                <>
                  <span>&bull;</span>
                  {isGenerating ? (
                    <span className="text-orange-600 dark:text-orange-400 font-medium inline-flex items-center gap-1">
                      <Loader2 className="size-2.5 animate-spin" />
                      <span>Cập nhật...</span>
                    </span>
                  ) : (
                    <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                      {totalPages} trang A4
                    </span>
                  )}
                </>
              )}
            </div>
          </div>
        </div>

        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 rounded-lg text-muted-foreground hover:text-foreground shrink-0"
          onClick={onClose}
          aria-label={t('modal.close', 'Đóng')}
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Row 2: Full-width Segmented View Switcher (Only in Studio mode) */}
      {wizardStep === 'studio' && (
        <div className="grid grid-cols-2 p-0.5 bg-background rounded-lg border border-border/80 text-xs font-semibold">
          <button
            type="button"
            onClick={() => setMobileView('controls')}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md transition-all ${
              mobileView === 'controls'
                ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Sliders className="size-3.5 shrink-0" />
            <span>{t('modal.mobile_config', 'Cấu hình')}</span>
          </button>
          <button
            type="button"
            onClick={() => setMobileView('preview')}
            className={`flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-md transition-all ${
              mobileView === 'preview'
                ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            <Eye className="size-3.5 shrink-0" />
            <span>{t('modal.mobile_preview', { count: totalPages, defaultValue: `Xem bản in (${totalPages})` })}</span>
          </button>
        </div>
      )}
    </DialogHeader>
  )
}

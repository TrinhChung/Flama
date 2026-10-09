import { ChevronLeft, ChevronRight, FileText, Loader2, Printer, ZoomIn, ZoomOut } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import type { DeckWorksheetMeta, WorksheetFieldMapping, WorksheetLayoutOptions, WorksheetPreviewResponse } from '../../types'
import { WorksheetPageRenderer } from '../WorksheetPageRenderer'

export function getFitZoom(orientation?: 'portrait' | 'landscape', customWidth?: number): number {
  const isLandscape = orientation === 'landscape'
  const a4WidthPx = (isLandscape ? 297 : 210) * 3.7795
  const winWidth = typeof window !== 'undefined' ? (customWidth || window.innerWidth) : 360
  const padding = winWidth < 640 ? 24 : winWidth < 1024 ? 40 : 64
  const availableWidth = Math.max(220, (winWidth < 768 ? winWidth : winWidth - 420) - padding)
  const fit = Math.floor((availableWidth / a4WidthPx) * 100) / 100
  return Math.min(1.4, Math.max(0.25, fit))
}

export interface StudioPreviewCanvasProps {
  mobileView: 'controls' | 'preview'
  currentPageIdx: number
  setCurrentPageIdx: React.Dispatch<React.SetStateAction<number>>
  previewData: WorksheetPreviewResponse | null
  zoomLevel: number
  setZoomLevel: React.Dispatch<React.SetStateAction<number>>
  layoutOptions: WorksheetLayoutOptions
  isGenerating: boolean
  isLoadingMeta: boolean
  currentTemplate: DeckWorksheetMeta['templates'][0] | null
  fieldMapping: WorksheetFieldMapping
  containerWidthPx: number
  containerHeightPx: number
  a4WidthMm: number
  a4HeightMm: number
  handleCanvasTouchEnd: (e: React.TouchEvent) => void
  handlePrint: () => Promise<void>
  isPrinting: boolean
}

export function StudioPreviewCanvas({
  mobileView,
  currentPageIdx,
  setCurrentPageIdx,
  previewData,
  zoomLevel,
  setZoomLevel,
  layoutOptions,
  isGenerating,
  isLoadingMeta,
  currentTemplate,
  fieldMapping,
  containerWidthPx,
  containerHeightPx,
  a4WidthMm,
  a4HeightMm,
  handleCanvasTouchEnd,
  handlePrint,
  isPrinting,
}: StudioPreviewCanvasProps) {
  const { t } = useTranslation('worksheets')

  return (
    <main
      className={`flex-1 flex flex-col bg-slate-200/90 dark:bg-slate-950 min-h-0 min-w-0 w-full max-w-full overflow-hidden relative ${
        mobileView === 'preview' ? 'flex' : 'hidden md:flex'
      }`}
    >
      {/* Workbench Top Bar (Page Navigation & Live Stats & Zoom Controls) */}
      <div className="w-full max-w-full px-2.5 sm:px-4 py-2 bg-background/80 backdrop-blur-xs border-b border-border/70 flex items-center justify-between gap-1.5 sm:gap-3 shrink-0 z-10">
        {/* Page Navigator */}
        <div className="flex items-center gap-1 sm:gap-1.5">
          <Button
            variant="outline"
            size="sm"
            disabled={currentPageIdx === 0 || !previewData}
            onClick={() => setCurrentPageIdx((p) => Math.max(0, p - 1))}
            className="h-7.5 px-2 text-xs font-semibold gap-1"
          >
            <ChevronLeft className="size-3.5" />
            <span className="hidden sm:inline">{t('studio.preview.prev_page', 'Trang trước')}</span>
          </Button>

          {/* Page Selector */}
          <div className="flex items-center gap-1 px-1 text-xs font-bold text-foreground shrink-0">
            <span className="hidden sm:inline">Trang</span>
            {previewData && previewData.total_pages > 1 ? (
              <NativeSelect
                size="sm"
                value={currentPageIdx}
                onChange={(e) => setCurrentPageIdx(Number(e.target.value))}
                className="h-7 w-14 sm:w-16 [&_select]:pr-5 [&_select]:pl-2 [&_select]:text-xs [&_select]:text-center font-bold"
              >
                {Array.from({ length: previewData.total_pages }).map((_, idx) => (
                  <option key={idx} value={idx}>
                    {idx + 1}
                  </option>
                ))}
              </NativeSelect>
            ) : (
              <span className="px-1">1</span>
            )}
            <span className="text-muted-foreground font-medium">/ {previewData?.total_pages || 1}</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            disabled={!previewData || currentPageIdx >= previewData.total_pages - 1}
            onClick={() =>
              setCurrentPageIdx((p) =>
                Math.min((previewData?.total_pages || 1) - 1, p + 1)
              )
            }
            className="h-7.5 px-2 text-xs font-semibold gap-1"
          >
            <span className="hidden sm:inline">{t('studio.preview.next_page', 'Trang sau')}</span>
            <ChevronRight className="size-3.5" />
          </Button>
        </div>

        {/* Right: Mobile Zoom Toolbar & Stats */}
        <div className="flex items-center gap-1.5">
          {/* Mobile/Tablet Zoom Toolbar */}
          <div className="flex md:hidden items-center bg-background rounded-lg border border-border/80 px-0.5 py-0.5 shadow-2xs">
            <Button
              variant="ghost"
              size="icon"
              className="size-6"
              onClick={() => setZoomLevel((z) => Math.max(0.25, Number((z - 0.08).toFixed(2))))}
              title={t('modal.zoom_out', 'Thu nhỏ')}
            >
              <ZoomOut className="size-3" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-1.5 text-[11px] font-bold"
              onClick={() => setZoomLevel(getFitZoom(layoutOptions.orientation))}
              title="Căn vừa màn hình"
            >
              {Math.round(zoomLevel * 100)}%
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-6"
              onClick={() => setZoomLevel((z) => Math.min(1.5, Number((z + 0.08).toFixed(2))))}
              title={t('modal.zoom_in', 'Phóng to')}
            >
              <ZoomIn className="size-3" />
            </Button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setZoomLevel(getFitZoom(layoutOptions.orientation))}
            className="flex md:hidden h-7 px-2 text-[11px] font-semibold"
          >
            {t('modal.zoom_fit', 'Vừa trang')}
          </Button>

          {isGenerating && (
            <Badge variant="outline" className="text-[11px] gap-1 text-primary animate-pulse bg-primary/5">
              <Loader2 className="size-3 animate-spin" />
              {t('studio.preview.updating', 'Đang cập nhật...')}
            </Badge>
          )}
          {previewData && (
            <Badge variant="secondary" className="hidden sm:inline-flex text-xs font-semibold px-2.5 py-0.5">
              {t('studio.preview.items_summary', {
                items: previewData.total_items,
                pages: previewData.total_pages,
                defaultValue: `Tổng: ${previewData.total_items} mục • ${previewData.total_pages} trang A4`,
              })}
            </Badge>
          )}
        </div>
      </div>

      {/* Canvas Scrollable Viewport */}
      <div
        onTouchEnd={handleCanvasTouchEnd}
        className="flex-1 overflow-auto p-2 sm:p-6 min-h-0 select-none relative flex flex-col items-center"
      >
        {isLoadingMeta || (isGenerating && !previewData) ? (
          <div className="m-auto flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Loader2 className="size-8 animate-spin text-primary" />
            <span className="text-xs font-medium">
              {isLoadingMeta
                ? t('studio.preview.loading_meta', 'Đang tải cấu hình thẻ học...')
                : t('studio.preview.preparing_pages', 'Đang chuẩn bị trang bài tập...')}
            </span>
          </div>
        ) : previewData && previewData.pages.length > 0 && previewData.pages[currentPageIdx] && currentTemplate ? (
          <div
            style={{
              width: `${containerWidthPx}px`,
              height: `${containerHeightPx}px`,
            }}
            className="relative shrink-0 transition-all duration-150 my-auto sm:my-0 shadow-md"
          >
            <div
              style={{
                transform: `scale(${zoomLevel})`,
                transformOrigin: 'top left',
                width: `${a4WidthMm}mm`,
                height: `${a4HeightMm}mm`,
              }}
              className="absolute top-0 left-0"
            >
              <WorksheetPageRenderer
                page={previewData.pages[currentPageIdx]}
                template={currentTemplate}
                options={layoutOptions}
                fieldMapping={fieldMapping}
                zoom={1}
              />
            </div>
          </div>
        ) : (
          <div className="m-auto py-16 text-center text-muted-foreground text-xs space-y-2">
            <FileText className="size-10 mx-auto text-muted-foreground/40" />
            <p>
              {t(
                'studio.preview.no_preview_warning',
                'Không có dữ liệu trang xem trước. Vui lòng kiểm tra lại ánh xạ trường dữ liệu.'
              )}
            </p>
          </div>
        )}
      </div>

      {/* Mobile Bottom Floating Action Bar for Preview */}
      <div className="w-full max-w-full flex md:hidden items-center justify-end gap-2 p-2 border-t border-border/80 bg-background/95 backdrop-blur-md shrink-0">
        <Button
          type="button"
          size="sm"
          onClick={handlePrint}
          disabled={isPrinting || !previewData}
          className="flex-1 max-w-[170px] h-9 px-3 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-md shrink-0"
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
      </div>
    </main>
  )
}

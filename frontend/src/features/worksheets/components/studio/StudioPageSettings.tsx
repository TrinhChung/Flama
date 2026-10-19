import { useTranslation } from 'react-i18next'
import {
  Minus,
  Plus,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Badge } from '@/components/ui/badge'
import { getFitZoom } from './StudioPreviewCanvas'
import type { StudioLayoutTabProps } from './StudioLayoutTab'

export function StudioPageSettings({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
  previewData,
  setZoomLevel,
}: Pick<
  StudioLayoutTabProps,
  | 'currentTemplate'
  | 'layoutOptions'
  | 'setLayoutOptions'
  | 'previewData'
  | 'setZoomLevel'
>) {
  const { t } = useTranslation('worksheets')
  if (!currentTemplate) return null

  return (
    <>
                      {/* Orientation & Page Margins */}
                      <div className="space-y-3 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
                        <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                          Khổ giấy & Hướng in A4
                        </h4>

                        {/* Orientation Toggle */}
                        <div className="grid grid-cols-2 gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'portrait' }))
                              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                                setZoomLevel?.(getFitZoom('portrait'))
                              }
                            }}
                            className={`flex flex-col items-center justify-center p-2 rounded-lg border text-xs font-medium transition-all ${
                              layoutOptions.orientation === 'portrait'
                                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                            }`}
                          >
                            <div className="w-4 h-6 border-2 border-current rounded-xs mb-1" />
                            <span>A4 Dọc (Portrait)</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setLayoutOptions((prev) => ({ ...prev, orientation: 'landscape' }))
                              if (typeof window !== 'undefined' && window.innerWidth < 768) {
                                setZoomLevel?.(getFitZoom('landscape'))
                              }
                            }}
                            className={`flex flex-col items-center justify-center p-2 rounded-lg border text-xs font-medium transition-all ${
                              layoutOptions.orientation === 'landscape'
                                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                            }`}
                          >
                            <div className="w-6 h-4 border-2 border-current rounded-xs mb-1.5" />
                            <span>A4 Ngang (Landscape)</span>
                          </button>
                        </div>

                        {/* Page Fill Mode: Balanced Stretch vs Max Density */}
                        <div className="space-y-2 pt-1 border-t border-border/50">
                          <Label className="text-xs font-bold text-foreground uppercase tracking-wider block">
                            Mật độ & Bố cục lấp đầy A4
                          </Label>
                          <div className="grid grid-cols-2 gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  page_fill_mode: 'balanced_stretch',
                                  auto_fit_page: true,
                                }))
                                toast.success('Đã chọn: Dàn đều kín trang (Đỡ mỏi tay, tự giãn khoảng cách dòng)')
                              }}
                              className={`flex flex-col p-2.5 rounded-lg border text-left transition-all ${
                                layoutOptions.page_fill_mode === 'balanced_stretch'
                                  ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                  : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                              }`}
                            >
                              <div className="text-xs font-bold flex items-center gap-1.5 text-foreground">
                                <span>🌿 Dàn đều kín trang</span>
                                {layoutOptions.page_fill_mode === 'balanced_stretch' && (
                                  <span className="text-[10px] text-primary">●</span>
                                )}
                              </div>
                              <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                                {layoutOptions.orientation === 'landscape' ? '6-7 từ/trang' : '8-10 từ/trang'}, tự giãn đều 100% không để trống đáy
                              </p>
                            </button>

                            <button
                              type="button"
                              onClick={() => {
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  page_fill_mode: 'max_density',
                                  auto_fit_page: true,
                                  box_size: prev.box_size && prev.box_size > 34 ? 32 : prev.box_size,
                                }))
                                toast.success('Đã chọn: Tiết kiệm giấy (Tối đa dòng, lấp kịch khung A4)')
                              }}
                              className={`flex flex-col p-2.5 rounded-lg border text-left transition-all ${
                                (layoutOptions.page_fill_mode || 'max_density') === 'max_density'
                                  ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                                  : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                              }`}
                            >
                              <div className="text-xs font-bold flex items-center gap-1.5 text-foreground">
                                <span>⚡ {t('studio.layout_tab.preset_save_paper', 'Tiết kiệm giấy')}</span>
                                {(layoutOptions.page_fill_mode || 'max_density') === 'max_density' && (
                                  <span className="text-[10px] text-primary">●</span>
                                )}
                              </div>
                              <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">
                                {layoutOptions.orientation === 'landscape' ? '12-14 từ/trang' : '18-20 từ/trang'}, phủ kín tối đa số từ
                              </p>
                            </button>
                          </div>
                        </div>

                        {/* Auto-fit A4 Mode vs Manual Rows per page */}
                        <div className="space-y-2 pt-1 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.auto_fit_page !== false}
                                onChange={(e) => {
                                  const isChecked = e.target.checked
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    auto_fit_page: isChecked,
                                    rows_per_page: !isChecked
                                      ? (previewData?.options?.rows_per_page ?? prev.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8)
                                      : prev.rows_per_page,
                                  }))
                                }}
                                className="rounded text-primary size-4"
                              />
                              <div>
                                <div className="text-xs font-bold text-foreground flex items-center gap-1.5">
                                  <span>⚡ Tự tính số dòng Full trang A4</span>
                                  <Badge variant="outline" className="text-[9px] bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
                                    Tối ưu
                                  </Badge>
                                </div>
                                <p className="text-[10px] text-muted-foreground">
                                  Tự động phủ kín 100% trang A4 theo hướng in & dòng trống
                                </p>
                              </div>
                            </label>
                          </div>

                          {layoutOptions.auto_fit_page !== false && (
                            <div className="pl-6 pt-1">
                              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-[11px] font-medium text-emerald-700 dark:text-emerald-300">
                                <span>⚡ Đang áp dụng:</span>
                                <strong className="font-bold">
                                  {previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8} dòng/trang
                                </strong>
                                <span className="text-muted-foreground text-[10px]">
                                  ({previewData?.total_pages ?? 1} trang A4)
                                </span>
                              </div>
                            </div>
                          )}

                          {layoutOptions.auto_fit_page === false && (
                            <div className="space-y-1.5 pl-6 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Tuỳ chỉnh số dòng mỗi trang:</Label>
                              </div>
                              <div className="flex items-center gap-1.5">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="size-8 shrink-0"
                                  onClick={() =>
                                    setLayoutOptions((prev) => {
                                      const current = prev.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8
                                      return {
                                        ...prev,
                                        rows_per_page: Math.max(1, current - 1),
                                      }
                                    })
                                  }
                                >
                                  <Minus className="size-3.5" />
                                </Button>
                                <div className="h-8 flex-1 flex items-center justify-center bg-muted/40 rounded-md border border-border text-xs font-bold text-foreground">
                                  {layoutOptions.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8} dòng/trang
                                </div>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="icon"
                                  className="size-8 shrink-0"
                                  onClick={() =>
                                    setLayoutOptions((prev) => {
                                      const current = prev.rows_per_page ?? previewData?.options?.rows_per_page ?? currentTemplate?.default_rows_per_page ?? 8
                                      return {
                                        ...prev,
                                        rows_per_page: Math.min(30, current + 1),
                                      }
                                    })
                                  }
                                >
                                  <Plus className="size-3.5" />
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>

                        {/* Extra Blank Practice Rows */}
                        <div className="space-y-1.5 pt-2 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs font-bold text-foreground">
                              Dòng trống luyện viết bổ sung:
                            </Label>
                            <span className="text-[10px] text-primary font-semibold">
                              {layoutOptions.extra_blank_rows ? `+${layoutOptions.extra_blank_rows} dòng/mục` : 'Không thêm'}
                            </span>
                          </div>
                          <div className="grid grid-cols-4 gap-1.5">
                            {[
                              { label: '0 dòng', val: 0 },
                              { label: '+1 dòng', val: 1 },
                              { label: '+2 dòng', val: 2 },
                              { label: '+3 dòng', val: 3 },
                            ].map((opt) => (
                              <Button
                                key={opt.val}
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    extra_blank_rows: opt.val,
                                  }))
                                }
                                className={`h-7.5 text-xs ${
                                  (layoutOptions.extra_blank_rows ?? 0) === opt.val
                                    ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                    : 'bg-muted/30 text-muted-foreground hover:bg-muted/60'
                                }`}
                              >
                                {opt.label}
                              </Button>
                            ))}
                          </div>
                          <p className="text-[10px] text-muted-foreground">
                            Thêm dải ô trống hoàn chỉnh bên dưới mỗi chữ để viết thêm nhiều lần.
                          </p>
                        </div>

                        {/* Fill Blank Rows at end of sheet */}
                        <div className="pt-2 border-t border-border/50">
                          <label className="flex items-center gap-2 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={layoutOptions.fill_blank_rows !== false}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  fill_blank_rows: e.target.checked,
                                }))
                              }
                              className="rounded text-primary size-4"
                            />
                            <div>
                              <div className="text-xs font-semibold text-foreground">
                                Điền đầy trang cuối bằng dòng trống
                              </div>
                              <p className="text-[10px] text-muted-foreground">
                                Tận dụng 100% diện tích giấy in, không để trống chân trang khi photo
                              </p>
                            </div>
                          </label>
                        </div>

                        {/* Margins */}
                        <div className="space-y-1.5 pt-2 border-t border-border/50">
                          <div className="flex items-center justify-between">
                            <Label className="text-xs font-semibold">Căn lề trang (Margins):</Label>
                            <Badge variant="secondary" className="text-[10px] font-bold text-primary">
                              {layoutOptions.margin === 'minimal' || layoutOptions.margin === 'ultra_compact'
                                ? '4mm (Siêu tiết kiệm)'
                                : layoutOptions.margin === 'compact'
                                ? '6mm (Thu gọn)'
                                : layoutOptions.margin === 'wide'
                                ? '14mm (Rộng)'
                                : '10mm (Chuẩn)'}
                            </Badge>
                          </div>
                          <NativeSelect
                            value={layoutOptions.margin || 'compact'}
                            onChange={(e) =>
                              setLayoutOptions((prev) => ({
                                ...prev,
                                margin: e.target.value as any,
                              }))
                            }
                            className="h-8.5 text-xs font-medium"
                          >
                            <option value="minimal">Siêu nhỏ (4mm - Tiết kiệm giấy tối đa, khai thác 98% A4)</option>
                            <option value="compact">Thu gọn (6mm - Gọn gàng, tiết kiệm giấy)</option>
                            <option value="standard">Tiêu chuẩn (10mm - Cân đối, phổ thông)</option>
                            <option value="wide">Rộng (14mm - Đóng gáy hồ sơ / kẹp tài liệu)</option>
                          </NativeSelect>
                        </div>
                      </div>
    </>
  )
}

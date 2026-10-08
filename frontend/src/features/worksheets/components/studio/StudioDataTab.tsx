import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import type { DeckWorksheetMeta, WorksheetFieldMapping, WorksheetLayoutOptions } from '../../types'

export interface StudioDataTabProps {
  isStandalone?: boolean
  deckId?: number | null
  currentTemplate: DeckWorksheetMeta['templates'][0] | null
  scope: 'all' | 'first_n' | 'random_n' | 'selected'
  setScope: (scope: 'all' | 'first_n' | 'random_n' | 'selected') => void
  limitCount: number
  setLimitCount: (count: number) => void
  initialCardIds?: (string | number)[]
  meta: DeckWorksheetMeta | null
  selectedNoteTypeId: string
  setSelectedNoteTypeId: (id: string) => void
  availableFields: string[]
  fieldMapping: WorksheetFieldMapping
  setFieldMapping: React.Dispatch<React.SetStateAction<WorksheetFieldMapping>>
  layoutOptions: WorksheetLayoutOptions
  setLayoutOptions: React.Dispatch<React.SetStateAction<WorksheetLayoutOptions>>
}

export function StudioDataTab({
  isStandalone,
  deckId,
  currentTemplate,
  scope,
  setScope,
  limitCount,
  setLimitCount,
  initialCardIds,
  meta,
  selectedNoteTypeId,
  setSelectedNoteTypeId,
  availableFields,
  fieldMapping,
  setFieldMapping,
  layoutOptions,
  setLayoutOptions,
}: StudioDataTabProps) {
  const { t } = useTranslation('worksheets')

  if (!currentTemplate) return null

  return (
    <div className="space-y-4">
      {!deckId || isStandalone ? (
        <div className="space-y-3 bg-card p-4 rounded-xl border border-border/70 shadow-xs">
          <div className="flex items-center gap-2 text-xs font-bold text-foreground uppercase tracking-wider">
            <span>📄 Mẫu giấy in độc lập</span>
            <Badge variant="outline" className="text-[9px] bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30">
              Không cần chọn Deck
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Bạn đang ở chế độ tạo mẫu giấy in tự do (ví dụ: giấy làm văn Genkō Yōshi 400 ô, ô kẻ chữ Hán, ô chữ thập). Toàn bộ trang giấy được tạo sẵn để in ra viết tay hoặc điền văn bản mẫu mà không cần kết nối tới bất kỳ bộ thẻ học nào.
          </p>
          <div className="text-[11px] text-muted-foreground bg-muted/40 p-3 rounded-lg border border-border/60 space-y-1">
            <div className="font-semibold text-foreground">💡 Mẹo tuỳ biến:</div>
            <div>• Chuyển sang tab <strong>Bố cục & Ô chữ</strong> để đổi khổ 400 ô / 200 ô, kiểu ô trơn / chữ thập, màu mực.</div>
            <div>• Chuyển sang tab <strong>Tiêu đề & Thông tin</strong> để đặt tiêu đề bài văn (sẽ tự động in vào dòng 1) hoặc đổi khung tên học sinh.</div>
          </div>
        </div>
      ) : (
        <>
          {/* Scope & Limit */}
          <div className="space-y-2.5 bg-muted/30 p-3.5 rounded-xl border border-border/60">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold text-foreground uppercase tracking-wider">
                {t('studio.data_tab.scope_label', 'Phạm vi dữ liệu')}
              </Label>
              <Badge variant="secondary" className="text-[10px] font-semibold">
                {scope === 'all'
                  ? `Toàn bộ (${meta?.total_notes || 0} ghi chú)`
                  : scope === 'selected'
                  ? `${initialCardIds?.length || 0} thẻ đã chọn`
                  : `${limitCount} ghi chú`}
              </Badge>
            </div>

            <div className="space-y-2">
              <NativeSelect
                value={scope}
                onChange={(e) => setScope(e.target.value as any)}
                className="h-8.5 text-xs"
              >
                {initialCardIds && initialCardIds.length > 0 && (
                  <option value="selected">
                    {initialCardIds.length} thẻ đang chọn trong danh sách
                  </option>
                )}
                <option value="all">Toàn bộ bộ thẻ ({meta?.total_notes} ghi chú)</option>
                <option value="first_n">N thẻ đầu tiên</option>
                <option value="random_n">Lấy ngẫu nhiên N thẻ</option>
              </NativeSelect>

              {(scope === 'first_n' || scope === 'random_n') && (
                <div className="space-y-1.5 pt-1">
                  <Label className="text-[11px] font-medium text-muted-foreground">
                    Số lượng ghi chú (N):
                  </Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      type="number"
                      min={1}
                      max={500}
                      value={limitCount}
                      onChange={(e) => setLimitCount(Math.max(1, Number(e.target.value)))}
                      className="h-8 text-xs w-20"
                    />
                    {[10, 20, 50, 100].map((cnt) => (
                      <Button
                        key={cnt}
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setLimitCount(cnt)}
                        className={`h-8 px-2 text-[11px] ${
                          limitCount === cnt ? 'bg-primary text-primary-foreground font-bold' : ''
                        }`}
                      >
                        {cnt}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Note Type Selector if multiple */}
          {meta && meta.note_types.length > 1 && (
            <div className="space-y-1.5 bg-muted/30 p-3.5 rounded-xl border border-border/60">
              <Label className="text-xs font-semibold">
                {t('studio.data_tab.note_type_label', 'Loại ghi chú (Note Type)')}
              </Label>
              <NativeSelect
                value={selectedNoteTypeId}
                onChange={(e) => setSelectedNoteTypeId(e.target.value)}
                className="h-8.5 text-xs"
              >
                {meta.note_types.map((nt) => (
                  <option key={nt.id} value={nt.id}>
                    {nt.name} ({nt.note_count} ghi chú)
                  </option>
                ))}
              </NativeSelect>
            </div>
          )}

          {/* Field Slots Mapping */}
          <div className="space-y-3 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                Ánh xạ trường nguồn
              </h4>
              <Badge variant="outline" className="text-[10px] text-muted-foreground">
                {availableFields.length} trường
              </Badge>
            </div>

            {currentTemplate.id === 'genkouyoushi' && layoutOptions.content_mode === 'blank' ? (
              <div className="text-xs text-rose-800 dark:text-rose-200 bg-rose-500/10 border border-rose-500/20 p-3.5 rounded-xl leading-relaxed space-y-2">
                <div className="font-bold flex items-center gap-1.5">
                  <span>📝 Chế độ: Trang trắng luyện viết tay (400 ô)</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Trang giấy sẽ được tạo trống hoàn toàn theo chuẩn giấy làm văn Genkō Yōshi (作文纸) để in ra luyện viết tay bằng bút mực. Bạn không cần ánh xạ trường dữ liệu nào từ thẻ.
                </p>
              </div>
            ) : currentTemplate.id === 'deck_table' ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <Label className="text-[11px] font-bold text-foreground">Chọn các cột bảng:</Label>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-semibold">
                      {((fieldMapping.custom_columns as string[]) || []).length} cột
                    </Badge>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[10px] px-1.5 text-primary hover:bg-primary/10"
                      onClick={() =>
                        setFieldMapping((prev) => ({
                          ...prev,
                          custom_columns: [...availableFields],
                        }))
                      }
                    >
                      Tất cả
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-6 text-[10px] px-1.5 text-muted-foreground hover:bg-muted"
                      onClick={() =>
                        setFieldMapping((prev) => ({
                          ...prev,
                          custom_columns: [],
                        }))
                      }
                    >
                      Bỏ chọn
                    </Button>
                  </div>
                </div>

                {((fieldMapping.custom_columns as string[]) || []).length === 0 && (
                  <div className="text-[11px] text-amber-700 dark:text-amber-300 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg leading-relaxed">
                    💡 <strong>Chưa chọn cột nào để hiển thị</strong>. Tích chọn các trường bên dưới để thêm vào bảng in (tránh chọn quá nhiều làm vỡ layout).
                  </div>
                )}

                {/* Selected Columns with Width Adjustment */}
                {((fieldMapping.custom_columns as string[]) || []).length > 0 && (
                  <div className="space-y-2 p-2.5 rounded-xl border border-border/80 bg-muted/20">
                    <Label className="text-[11px] font-bold text-foreground block">
                      Độ rộng từng cột đã chọn:
                    </Label>
                    <div className="space-y-2">
                      {((fieldMapping.custom_columns as string[]) || []).map((colName) => {
                        const currentW = (layoutOptions.column_widths || {})[colName]
                        return (
                          <div
                            key={colName}
                            className="p-2 rounded-lg border border-border bg-background space-y-1.5 shadow-2xs"
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-foreground truncate max-w-[180px]">
                                {colName}
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  const currentCols = (fieldMapping.custom_columns as string[]) || []
                                  setFieldMapping((prev) => ({
                                    ...prev,
                                    custom_columns: currentCols.filter((c) => c !== colName),
                                  }))
                                }}
                                className="text-muted-foreground hover:text-destructive p-0.5 rounded transition-colors"
                                title="Xóa cột này"
                              >
                                <X className="size-3.5" />
                              </button>
                            </div>
                            <div className="flex items-center gap-1 overflow-x-auto pb-0.5">
                              {['Auto', '15%', '20%', '25%', '30%', '40%'].map((wOpt) => {
                                const isAuto = wOpt === 'Auto'
                                const isSelected = isAuto
                                  ? !currentW
                                  : currentW === wOpt || currentW === parseInt(wOpt, 10)
                                return (
                                  <button
                                    key={wOpt}
                                    type="button"
                                    onClick={() => {
                                      setLayoutOptions((prev) => {
                                        const nextWidths = { ...(prev.column_widths || {}) }
                                        if (isAuto) {
                                          delete nextWidths[colName]
                                        } else {
                                          nextWidths[colName] = wOpt
                                        }
                                        return { ...prev, column_widths: nextWidths }
                                      })
                                    }}
                                    className={`flex-1 text-[10px] py-0.5 rounded border font-medium transition-colors ${
                                      isSelected
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-muted/40 text-muted-foreground hover:bg-muted border-border/70'
                                    }`}
                                  >
                                    {wOpt}
                                  </button>
                                )
                              })}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Available Fields Picker Checkboxes */}
                <div className="space-y-1.5">
                  <Label className="text-[11px] font-semibold text-muted-foreground block">
                    Danh sách trường trong Note Type:
                  </Label>
                  <div className="grid grid-cols-2 gap-1.5">
                    {availableFields.map((f) => {
                      const currentCols = (fieldMapping.custom_columns as string[]) || []
                      const isChecked = currentCols.includes(f)
                      return (
                        <label
                          key={f}
                          className={`flex items-center gap-1.5 p-2 rounded-lg border text-xs cursor-pointer transition-all ${
                            isChecked
                              ? 'border-primary bg-primary/5 text-foreground font-semibold shadow-2xs'
                              : 'border-border bg-muted/20 hover:bg-muted/40 text-muted-foreground'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setFieldMapping((prev) => ({
                                  ...prev,
                                  custom_columns: [...currentCols, f],
                                }))
                              } else {
                                setFieldMapping((prev) => ({
                                  ...prev,
                                  custom_columns: currentCols.filter((c) => c !== f),
                                }))
                              }
                            }}
                            className="rounded text-primary focus:ring-primary size-3.5"
                          />
                          <span className="truncate">{f}</span>
                        </label>
                      )
                    })}
                  </div>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {currentTemplate.field_slots.map((slot) => {
                  const val = (fieldMapping[slot.key] as string) || ''
                  return (
                    <div key={slot.key} className="space-y-1 p-2.5 rounded-xl border border-border/60 bg-muted/10">
                      <div className="flex items-center justify-between">
                        <Label className="text-xs font-semibold flex items-center gap-1.5">
                          <span>{slot.label_vi}</span>
                          {slot.required ? (
                            <Badge variant="outline" className="text-[9px] text-rose-500 border-rose-200 bg-rose-50 px-1 py-0 font-bold">
                              Bắt buộc
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-[9px] text-muted-foreground border-border px-1 py-0 font-normal">
                              Tùy chọn
                            </Badge>
                          )}
                        </Label>
                        {!slot.required && val && (
                          <button
                            type="button"
                            onClick={() =>
                              setFieldMapping((prev) => ({
                                ...prev,
                                [slot.key]: '',
                              }))
                            }
                            className="text-[10px] font-medium text-muted-foreground hover:text-rose-500 transition-colors"
                          >
                            Bỏ qua trường này
                          </button>
                        )}
                      </div>
                      <NativeSelect
                        value={val}
                        onChange={(e) =>
                          setFieldMapping((prev) => ({
                            ...prev,
                            [slot.key]: e.target.value,
                          }))
                        }
                        className={`h-8.5 text-xs ${
                          !val && !slot.required ? 'text-muted-foreground bg-background/50 border-dashed' : ''
                        }`}
                      >
                        <option value="">
                          {slot.required ? '-- Chọn trường nguồn (Bắt buộc) --' : '-- Bỏ trống (Không sử dụng trường này) --'}
                        </option>
                        {availableFields.map((f) => (
                          <option key={f} value={f}>
                            {f}
                          </option>
                        ))}
                      </NativeSelect>
                      {slot.description_vi && (
                        <p className="text-[10px] text-muted-foreground leading-tight">
                          {slot.description_vi}
                        </p>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

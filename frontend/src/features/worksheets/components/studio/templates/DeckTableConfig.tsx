import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

export function DeckTableConfig({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
}: Pick<
  StudioLayoutTabProps,
  'currentTemplate' | 'layoutOptions' | 'setLayoutOptions'
>) {
  if (!currentTemplate || currentTemplate.id !== 'deck_table') return null

  const isLandscape = layoutOptions.orientation === 'landscape'

  return (
    <>
                      {/* TABLE SPECIFIC OPTIONS (Generic Deck Table) */}
                      {currentTemplate.id === 'deck_table' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                              Cột phụ bổ sung (Luyện viết / Đánh giá)
                            </h4>
                            <Badge variant="outline" className="text-[10px] text-primary bg-primary/5">
                              Tuỳ biến
                            </Badge>
                          </div>

                          {/* Toggle auxiliary column */}
                          <div className="space-y-1.5">
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={
                                  layoutOptions.auxiliary_column_enabled !== undefined
                                    ? layoutOptions.auxiliary_column_enabled
                                    : layoutOptions.include_practice_column !== false
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    auxiliary_column_enabled: e.target.checked,
                                    include_practice_column: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-4"
                              />
                              <span className="text-xs font-bold text-foreground">
                                Bật cột phụ bổ sung ở cuối bảng
                              </span>
                            </label>
                            <p className="text-[10px] text-muted-foreground pl-6">
                              Thêm 1 cột để học sinh luyện viết, dịch nghĩa hoặc tự đánh giá bài làm.
                            </p>
                          </div>

                          {(layoutOptions.auxiliary_column_enabled !== undefined
                            ? layoutOptions.auxiliary_column_enabled
                            : layoutOptions.include_practice_column !== false) && (
                            <div className="space-y-3 p-3 rounded-xl border border-border/80 bg-muted/20">
                              {/* Auxiliary Column Title */}
                              <div className="space-y-1">
                                <Label className="text-xs font-semibold">Tên / Tiêu đề cột phụ:</Label>
                                <Input
                                  value={
                                    layoutOptions.auxiliary_column_title ??
                                    layoutOptions.practice_column_label ??
                                    'Ghi chú / Luyện viết'
                                  }
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      auxiliary_column_title: e.target.value,
                                      practice_column_label: e.target.value,
                                    }))
                                  }
                                  className="h-8 text-xs font-medium"
                                  placeholder="Ví dụ: Ghi chú, Luyện viết, Tự dịch, Đánh giá..."
                                />
                              </div>

                              {/* Auxiliary Column Types (5 basic types) */}
                              <div className="space-y-1.5">
                                <Label className="text-xs font-semibold">Kiểu hiển thị cột phụ:</Label>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                                  {[
                                    {
                                      id: 'dashed_line',
                                      label: '✍️ Dòng kẻ đứt',
                                      desc: 'Dòng kẻ ngang nét đứt để ghi chú / viết tự do',
                                    },
                                    {
                                      id: 'grid_boxes',
                                      label: '🔲 Ô kẻ ô chữ',
                                      desc: 'Dải ô vuông Genkō yōshi để tập viết chữ Hán',
                                    },
                                    {
                                      id: 'checkboxes',
                                      label: '☑️ Đánh dấu kiểm tra',
                                      desc: '3 ô tích [ ] 1  [ ] 2  [ ] 3 theo dõi tiến độ',
                                    },
                                    {
                                      id: 'double_line',
                                      label: '═ Dòng kẻ đôi',
                                      desc: '2 dòng kẻ song song để viết câu hoàn chỉnh',
                                    },
                                    {
                                      id: 'blank',
                                      label: '📄 Khung trắng',
                                      desc: 'Khoảng trống sạch sẽ không đường kẻ',
                                    },
                                  ].map((tOpt) => {
                                    const currentType = layoutOptions.auxiliary_column_type || 'dashed_line'
                                    const isSelected = currentType === tOpt.id
                                    return (
                                      <button
                                        key={tOpt.id}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_type: tOpt.id as any,
                                          }))
                                        }
                                        className={`flex flex-col text-left p-2 rounded-lg border transition-all ${
                                          isSelected
                                            ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                            : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                        }`}
                                      >
                                        <span className="text-xs">{tOpt.label}</span>
                                        <span className="text-[10px] text-muted-foreground font-normal line-clamp-1">
                                          {tOpt.desc}
                                        </span>
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>

                              {/* If Grid Boxes selected: Stepper to choose number of boxes */}
                              {layoutOptions.auxiliary_column_type === 'grid_boxes' && (
                                <div className="space-y-1 pt-1">
                                  <div className="flex items-center justify-between">
                                    <Label className="text-xs font-semibold">Số ô vuông kẻ ô mỗi dòng:</Label>
                                    <span className="text-xs font-bold text-primary">
                                      {layoutOptions.auxiliary_column_boxes_count ?? 4} ô
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5">
                                    {[2, 3, 4, 5, 6].map((num) => (
                                      <Button
                                        key={num}
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_boxes_count: num,
                                          }))
                                        }
                                        className={`flex-1 h-7.5 text-xs ${
                                          (layoutOptions.auxiliary_column_boxes_count ?? 4) === num
                                            ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                            : 'bg-background hover:bg-muted text-muted-foreground'
                                        }`}
                                      >
                                        {num} ô
                                      </Button>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Auxiliary Column Width */}
                              <div className="space-y-1.5 pt-1">
                                <div className="flex items-center justify-between">
                                  <Label className="text-xs font-semibold">Độ rộng cột phụ:</Label>
                                  <span className="text-xs font-bold text-primary">
                                    {layoutOptions.auxiliary_column_width || (isLandscape ? '25%' : '30%')}
                                  </span>
                                </div>
                                <div className="grid grid-cols-6 gap-1">
                                  {['15%', '20%', '25%', '30%', '35%', '40%'].map((wOpt) => {
                                    const defaultW = isLandscape ? '25%' : '30%'
                                    const currentW = layoutOptions.auxiliary_column_width || defaultW
                                    const isSelected = currentW === wOpt
                                    return (
                                      <button
                                        key={wOpt}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            auxiliary_column_width: wOpt,
                                          }))
                                        }
                                        className={`h-7 text-[11px] rounded border font-medium transition-colors ${
                                          isSelected
                                            ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                            : 'bg-background text-muted-foreground hover:bg-muted border-border'
                                        }`}
                                      >
                                        {wOpt}
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
    </>
  )
}

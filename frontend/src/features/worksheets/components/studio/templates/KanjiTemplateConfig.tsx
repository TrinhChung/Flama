import {
  Minus,
  Plus,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Badge } from '@/components/ui/badge'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

export function KanjiTemplateConfig({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
  meta,
}: Pick<
  StudioLayoutTabProps,
  'currentTemplate' | 'layoutOptions' | 'setLayoutOptions' | 'meta'
>) {
  if (!currentTemplate || currentTemplate.category !== 'kanji') return null

  return (
    <>
                      {/* Kanji Grid & Practice Box Options */}
                      {currentTemplate.category === 'kanji' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Ô chữ & Nét bút Kanji
                          </h4>

                          {/* Box Size Control */}
                          <div className="space-y-1.5 pt-1">
                            <div className="flex items-center justify-between">
                              <Label className="text-xs font-semibold">Kích thước ô viết:</Label>
                              <span className="text-[10px] text-primary font-bold">
                                {layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)}px
                              </span>
                            </div>
                            <div className="grid grid-cols-4 gap-1">
                              {[
                                { label: '18px', val: 18 },
                                { label: '28px', val: 28 },
                                { label: '36px', val: 36 },
                                { label: '44px', val: 44 },
                              ].map((preset) => (
                                <Button
                                  key={preset.val}
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      box_size: preset.val,
                                    }))
                                  }
                                  className={`h-7 text-xs ${
                                    (layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)) === preset.val
                                      ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                      : 'bg-background hover:bg-muted text-muted-foreground'
                                  }`}
                                >
                                  {preset.label}
                                </Button>
                              ))}
                            </div>
                            <div className="flex items-center gap-1.5 pt-1">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-7.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    box_size: Math.max(10, (prev.box_size ?? 36) - 2),
                                  }))
                                }
                              >
                                <Minus className="size-3" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={10}
                                  max={120}
                                  value={layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_size: Math.max(10, Math.min(120, val)),
                                      }))
                                    }
                                  }}
                                  className="h-7.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">px</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-7.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    box_size: Math.min(120, (prev.box_size ?? 36) + 2),
                                  }))
                                }
                              >
                                <Plus className="size-3" />
                              </Button>
                            </div>
                            <p className="text-[10px] text-muted-foreground">
                              Tự do tuỳ chỉnh từ 10px trở lên. Ô càng nhỏ thì càng chứa được nhiều ô/dòng và nhiều dòng/trang.
                            </p>
                          </div>

                          {/* Grid Style Selection */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Kiểu đường kẻ ô:</Label>
                            <NativeSelect
                              value={layoutOptions.grid_style || 'cross'}
                              onChange={(e) =>
                                setLayoutOptions((prev) => ({
                                  ...prev,
                                  grid_style: e.target.value as any,
                                }))
                              }
                              className="h-8.5 text-xs"
                            >
                              <option value="cross">Ô chữ thập (+ / 田)</option>
                              <option value="diagonal">Ô hoa thị (米字格)</option>
                              <option value="square">Ô vuông trơn (□)</option>
                            </NativeSelect>
                          </div>

                          {/* Trace Count Stepper */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Số ô đồ chữ (mờ):</Label>
                            <div className="flex items-center gap-1.5">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    trace_count: Math.max(0, (prev.trace_count ?? 2) - 1),
                                  }))
                                }
                              >
                                <Minus className="size-3.5" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={0}
                                  max={30}
                                  value={layoutOptions.trace_count ?? 2}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        trace_count: Math.max(0, Math.min(30, val)),
                                      }))
                                    }
                                  }}
                                  className="h-8.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">ô</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    trace_count: Math.min(30, (prev.trace_count ?? 2) + 1),
                                  }))
                                }
                              >
                                <Plus className="size-3.5" />
                              </Button>
                            </div>
                          </div>

                          {/* Practice Count Stepper */}
                          <div className="space-y-1">
                            <Label className="text-xs font-semibold">Số ô tự viết (trống):</Label>
                            <div className="flex items-center gap-1.5">
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    practice_count: Math.max(1, (prev.practice_count ?? 6) - 1),
                                  }))
                                }
                              >
                                <Minus className="size-3.5" />
                              </Button>
                              <div className="flex-1 flex items-center gap-1">
                                <Input
                                  type="number"
                                  min={1}
                                  max={100}
                                  value={layoutOptions.practice_count ?? 6}
                                  onChange={(e) => {
                                    const val = parseInt(e.target.value, 10)
                                    if (!isNaN(val)) {
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_count: Math.max(1, Math.min(100, val)),
                                      }))
                                    }
                                  }}
                                  className="h-8.5 text-xs text-center font-bold"
                                />
                                <span className="text-xs font-semibold text-muted-foreground">ô</span>
                              </div>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="size-8.5 shrink-0"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    practice_count: Math.min(100, (prev.practice_count ?? 6) + 1),
                                  }))
                                }
                              >
                                <Plus className="size-3.5" />
                              </Button>
                            </div>
                          </div>

                          {/* Color & Stroke Settings */}
                          <div className="space-y-3 pt-2 border-t border-border/60">
                            {/* Ngôn ngữ & Bộ nét chữ Hán */}
                            <div className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <Label className="text-[11px] font-semibold text-foreground">
                                  Bộ nét & Ngôn ngữ chữ Hán:
                                </Label>
                                {meta?.detected_locale && (
                                  <Badge variant="outline" className="text-[9.5px] px-1.5 py-0 h-4.5 bg-primary/5 text-primary border-primary/20">
                                    Tự động: {meta.detected_locale === 'zh' ? 'Tiếng Trung' : meta.detected_locale === 'zh-hant' ? 'Phồn thể' : 'Tiếng Nhật'}
                                  </Badge>
                                )}
                              </div>
                              <NativeSelect
                                value={layoutOptions.locale || meta?.detected_locale || 'ja'}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    locale: e.target.value as any,
                                  }))
                                }
                                className="h-8 text-xs bg-card"
                              >
                                <option value="ja">Tiếng Nhật (KanjiVG - Bộ nét chuẩn Nhật)</option>
                                <option value="zh">Tiếng Trung Giản thể (Make Me A Hanzi - Chuẩn HSK)</option>
                                <option value="zh-hant">Tiếng Trung Phồn thể (Make Me A Hanzi - Đài Loan / HK)</option>
                              </NativeSelect>
                            </div>
                            <div className="space-y-1.5">
                              <Label className="text-[11px] font-semibold text-foreground flex items-center justify-between">
                                <span>Màu chữ mẫu (Ô đầu tiên):</span>
                                <span
                                  className="size-3.5 rounded-full border border-border inline-block shrink-0 shadow-2xs"
                                  style={{ backgroundColor: layoutOptions.reference_char_color || '#e11d48' }}
                                />
                              </Label>
                              <div className="flex items-center gap-1.5 flex-wrap">
                                {[
                                  { label: 'Đỏ', color: '#e11d48' },
                                  { label: 'Xanh dương', color: '#2563eb' },
                                  { label: 'Xanh lá', color: '#16a34a' },
                                  { label: 'Cam', color: '#ea580c' },
                                  { label: 'Tím', color: '#9333ea' },
                                  { label: 'Đen', color: '#0f172a' },
                                ].map((p) => {
                                  const isSelected = (layoutOptions.reference_char_color || '#e11d48') === p.color
                                  return (
                                    <button
                                      key={p.color}
                                      type="button"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          reference_char_color: p.color,
                                        }))
                                      }
                                      className={`size-5 rounded-full transition-all flex items-center justify-center ${
                                        isSelected
                                          ? 'ring-2 ring-primary ring-offset-1 scale-110 shadow-xs'
                                          : 'opacity-70 hover:opacity-100 hover:scale-105'
                                      }`}
                                      style={{ backgroundColor: p.color }}
                                      title={p.label}
                                    >
                                      {isSelected && <span className="text-[9px] text-white font-bold leading-none">✓</span>}
                                    </button>
                                  )
                                })}
                                <label
                                  className="size-5 rounded-full border border-dashed border-border cursor-pointer flex items-center justify-center hover:bg-muted transition-colors relative overflow-hidden"
                                  title="Chọn màu tuỳ chỉnh"
                                >
                                  <span className="text-[10px] text-muted-foreground font-bold">🎨</span>
                                  <input
                                    type="color"
                                    value={layoutOptions.reference_char_color || '#e11d48'}
                                    onChange={(e) =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        reference_char_color: e.target.value,
                                      }))
                                    }
                                    className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                                  />
                                </label>
                              </div>
                            </div>

                            {(currentTemplate.id === 'kanji_compact' || currentTemplate.id === 'kanji_stroke') && (
                              <div className="space-y-1.5">
                                <Label className="text-[11px] font-semibold text-foreground block">
                                  Kiểu màu nét vẽ (Ô thứ 2):
                                </Label>
                                <div className="grid grid-cols-3 gap-1">
                                  {[
                                    {
                                      id: 'monochrome',
                                      label: 'Đen đơn sắc',
                                      icon: '🖤',
                                      hint: 'Rõ nét khi in/photo',
                                    },
                                    {
                                      id: 'multicolor',
                                      label: 'Đa màu sắc',
                                      icon: '🌈',
                                      hint: 'Phân biệt từng nét',
                                    },
                                    {
                                      id: 'same_as_reference',
                                      label: 'Theo chữ mẫu',
                                      icon: '🎨',
                                      hint: 'Đồng bộ màu sắc',
                                    },
                                  ].map((modeOpt) => {
                                    const isSelected =
                                      (layoutOptions.stroke_color_mode || 'monochrome') === modeOpt.id
                                    return (
                                      <button
                                        key={modeOpt.id}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            stroke_color_mode: modeOpt.id as any,
                                          }))
                                        }
                                        className={`px-1.5 py-1 rounded-md text-[10px] border font-medium flex flex-col items-center text-center transition-all ${
                                          isSelected
                                            ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                            : 'border-border/70 bg-card text-muted-foreground hover:bg-muted/50'
                                        }`}
                                        title={modeOpt.hint}
                                      >
                                        <span className="text-xs">{modeOpt.icon}</span>
                                        <span className="truncate w-full mt-0.5">{modeOpt.label}</span>
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            )}

                            {currentTemplate.id === 'kanji_step_by_step' && (
                              <div className="space-y-1.5">
                                <Label className="text-[11px] font-semibold text-foreground flex items-center justify-between">
                                  <span>Màu nét mới (Bước hiện tại - để tô theo):</span>
                                  <span
                                    className="size-3.5 rounded-full border border-border inline-block shrink-0 shadow-2xs"
                                    style={{ backgroundColor: layoutOptions.step_highlight_color || '#e11d48' }}
                                  />
                                </Label>
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  {[
                                    { label: 'Đỏ', color: '#e11d48' },
                                    { label: 'Xanh dương', color: '#2563eb' },
                                    { label: 'Xanh lá', color: '#16a34a' },
                                    { label: 'Cam', color: '#ea580c' },
                                    { label: 'Tím', color: '#9333ea' },
                                    { label: 'Đen', color: '#0f172a' },
                                  ].map((p) => {
                                    const isSelected = (layoutOptions.step_highlight_color || '#e11d48') === p.color
                                    return (
                                      <button
                                        key={p.color}
                                        type="button"
                                        onClick={() =>
                                          setLayoutOptions((prev) => ({
                                            ...prev,
                                            step_highlight_color: p.color,
                                          }))
                                        }
                                        className={`size-5 rounded-full transition-all flex items-center justify-center ${
                                          isSelected
                                            ? 'ring-2 ring-primary ring-offset-1 scale-110 shadow-xs'
                                            : 'opacity-70 hover:opacity-100 hover:scale-105'
                                        }`}
                                        style={{ backgroundColor: p.color }}
                                        title={p.label}
                                      >
                                        {isSelected && <span className="text-[9px] text-white font-bold leading-none">✓</span>}
                                      </button>
                                    )
                                  })}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Toggles */}
                          <div className="space-y-1.5 pt-2 border-t border-border/60 text-xs">
                            {currentTemplate.id === 'kanji_step_by_step' && (
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={Boolean(layoutOptions.show_step_numbers)}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_step_numbers: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện số thứ tự bước (1, 2, 3...)</span>
                              </label>
                            )}
                            {(currentTemplate.id === 'kanji_compact' || currentTemplate.id === 'kanji_stroke') && (
                              <>
                                <label className="flex items-center gap-2 cursor-pointer select-none">
                                  <input
                                    type="checkbox"
                                    checked={layoutOptions.show_stroke_diagram !== false}
                                    onChange={(e) =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        show_stroke_diagram: e.target.checked,
                                      }))
                                    }
                                    className="rounded text-primary size-3.5"
                                  />
                                  <span>Hiện sơ đồ nét bút SVG (Ô thứ 2)</span>
                                </label>
                                {layoutOptions.show_stroke_diagram !== false && (
                                  <label className="flex items-center gap-2 cursor-pointer select-none pl-3 border-l-2 border-primary/30">
                                    <input
                                      type="checkbox"
                                      checked={layoutOptions.show_stroke_numbers !== false}
                                      onChange={(e) =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          show_stroke_numbers: e.target.checked,
                                        }))
                                      }
                                      className="rounded text-primary size-3.5"
                                    />
                                    <span>Hiện số thứ tự nét 1, 2, 3...</span>
                                  </label>
                                )}
                              </>
                            )}
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={Boolean(layoutOptions.show_reading)}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_reading: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện Âm đọc</span>
                            </label>
                            <label className="flex items-center gap-2 cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={Boolean(layoutOptions.show_meaning)}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_meaning: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-3.5"
                              />
                              <span>Hiện Ý nghĩa</span>
                            </label>
                            {(currentTemplate.id === 'kanji_compact' ||
                              currentTemplate.id === 'kanji_stroke' ||
                              currentTemplate.id === 'kanji_step_by_step') && (
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={Boolean(layoutOptions.show_source_word)}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_source_word: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện Từ ví dụ</span>
                              </label>
                            )}
                          </div>
                        </div>
                      )}
    </>
  )
}

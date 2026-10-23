import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Badge } from '@/components/ui/badge'
import type { WorksheetLayoutOptions } from '../../../types'
import { ColorSwatchPicker } from '../controls/ColorSwatchPicker'
import { LayoutOptionCheckbox, OptionPill } from '../controls/LayoutOptionControls'
import { NumberStepper } from '../controls/NumberStepper'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

const BOX_SIZE_PRESETS = [18, 28, 36, 44]
const STROKE_COLOR_MODES: {
  id: NonNullable<WorksheetLayoutOptions['stroke_color_mode']>
  label: string
  icon: string
  hint: string
}[] = [
  { id: 'monochrome', label: 'Đen đơn sắc', icon: '🖤', hint: 'Rõ nét khi in/photo' },
  { id: 'multicolor', label: 'Đa màu sắc', icon: '🌈', hint: 'Phân biệt từng nét' },
  { id: 'same_as_reference', label: 'Theo chữ mẫu', icon: '🎨', hint: 'Đồng bộ màu sắc' },
]

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value))

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

  const isStrokeTemplate = currentTemplate.id === 'kanji_compact' || currentTemplate.id === 'kanji_stroke'
  const isStepTemplate = currentTemplate.id === 'kanji_step_by_step'
  const boxSize = layoutOptions.box_size ?? (currentTemplate.id === 'kanji_compact' ? 30 : 36)
  const referenceColor = layoutOptions.reference_char_color || '#e11d48'
  const stepHighlightColor = layoutOptions.step_highlight_color || '#e11d48'
  const setOption = <K extends keyof WorksheetLayoutOptions>(key: K, value: WorksheetLayoutOptions[K]) =>
    setLayoutOptions((prev) => ({ ...prev, [key]: value }))
  const checkboxProps = { layoutOptions, setLayoutOptions }

  return (
    <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
      <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
        Ô chữ & Nét bút Kanji
      </h4>

      {/* Box Size Control */}
      <div className="space-y-1.5 pt-1">
        <div className="flex items-center justify-between">
          <Label className="text-xs font-semibold">Kích thước ô viết:</Label>
          <span className="text-[10px] text-primary font-bold">
            {boxSize}px
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1">
          {BOX_SIZE_PRESETS.map((size) => (
            <OptionPill
              key={size}
              active={boxSize === size}
              onClick={() => setOption('box_size', size)}
              className="h-7 text-xs"
            >
              {`${size}px`}
            </OptionPill>
          ))}
        </div>
        <NumberStepper
          size="sm"
          className="flex items-center gap-1.5 pt-1"
          value={boxSize}
          min={10}
          max={120}
          unit="px"
          onDecrement={() =>
            setLayoutOptions((prev) => ({ ...prev, box_size: Math.max(10, (prev.box_size ?? 36) - 2) }))
          }
          onIncrement={() =>
            setLayoutOptions((prev) => ({ ...prev, box_size: Math.min(120, (prev.box_size ?? 36) + 2) }))
          }
          onValueChange={(val) => setOption('box_size', clamp(val, 10, 120))}
        />
        <p className="text-[10px] text-muted-foreground">
          Tự do tuỳ chỉnh từ 10px trở lên. Ô càng nhỏ thì càng chứa được nhiều ô/dòng và nhiều dòng/trang.
        </p>
      </div>

      {/* Grid Style Selection */}
      <div className="space-y-1">
        <Label className="text-xs font-semibold">Kiểu đường kẻ ô:</Label>
        <NativeSelect
          value={layoutOptions.grid_style || 'cross'}
          onChange={(e) => setOption('grid_style', e.target.value as WorksheetLayoutOptions['grid_style'])}
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
        <NumberStepper
          value={layoutOptions.trace_count ?? 2}
          min={0}
          max={30}
          unit="ô"
          onDecrement={() =>
            setLayoutOptions((prev) => ({ ...prev, trace_count: Math.max(0, (prev.trace_count ?? 2) - 1) }))
          }
          onIncrement={() =>
            setLayoutOptions((prev) => ({ ...prev, trace_count: Math.min(30, (prev.trace_count ?? 2) + 1) }))
          }
          onValueChange={(val) => setOption('trace_count', clamp(val, 0, 30))}
        />
      </div>

      {/* Practice Count Stepper */}
      <div className="space-y-1">
        <Label className="text-xs font-semibold">Số ô tự viết (trống):</Label>
        <NumberStepper
          value={layoutOptions.practice_count ?? 6}
          min={1}
          max={100}
          unit="ô"
          onDecrement={() =>
            setLayoutOptions((prev) => ({ ...prev, practice_count: Math.max(1, (prev.practice_count ?? 6) - 1) }))
          }
          onIncrement={() =>
            setLayoutOptions((prev) => ({ ...prev, practice_count: Math.min(100, (prev.practice_count ?? 6) + 1) }))
          }
          onValueChange={(val) => setOption('practice_count', clamp(val, 1, 100))}
        />
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
            onChange={(e) => setOption('locale', e.target.value as WorksheetLayoutOptions['locale'])}
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
              style={{ backgroundColor: referenceColor }}
            />
          </Label>
          <ColorSwatchPicker value={referenceColor} onChange={(color) => setOption('reference_char_color', color)}>
            <label
              className="size-5 rounded-full border border-dashed border-border cursor-pointer flex items-center justify-center hover:bg-muted transition-colors relative overflow-hidden"
              title="Chọn màu tuỳ chỉnh"
            >
              <span className="text-[10px] text-muted-foreground font-bold">🎨</span>
              <input
                type="color"
                value={referenceColor}
                onChange={(e) => setOption('reference_char_color', e.target.value)}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
            </label>
          </ColorSwatchPicker>
        </div>

        {isStrokeTemplate && (
          <div className="space-y-1.5">
            <Label className="text-[11px] font-semibold text-foreground block">
              Kiểu màu nét vẽ (Ô thứ 2):
            </Label>
            <div className="grid grid-cols-3 gap-1">
              {STROKE_COLOR_MODES.map((modeOpt) => {
                const isSelected = (layoutOptions.stroke_color_mode || 'monochrome') === modeOpt.id
                return (
                  <button
                    key={modeOpt.id}
                    type="button"
                    onClick={() => setOption('stroke_color_mode', modeOpt.id)}
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

        {isStepTemplate && (
          <div className="space-y-1.5">
            <Label className="text-[11px] font-semibold text-foreground flex items-center justify-between">
              <span>Màu nét mới (Bước hiện tại - để tô theo):</span>
              <span
                className="size-3.5 rounded-full border border-border inline-block shrink-0 shadow-2xs"
                style={{ backgroundColor: stepHighlightColor }}
              />
            </Label>
            <ColorSwatchPicker value={stepHighlightColor} onChange={(color) => setOption('step_highlight_color', color)} />
          </div>
        )}
      </div>

      {/* Toggles */}
      <div className="space-y-1.5 pt-2 border-t border-border/60 text-xs">
        {isStepTemplate && (
          <LayoutOptionCheckbox field="show_step_numbers" label="Hiện số thứ tự bước (1, 2, 3...)" defaultChecked={false} {...checkboxProps} />
        )}
        {isStrokeTemplate && (
          <>
            <LayoutOptionCheckbox field="show_stroke_diagram" label="Hiện sơ đồ nét bút SVG (Ô thứ 2)" defaultChecked={true} {...checkboxProps} />
            {layoutOptions.show_stroke_diagram !== false && (
              <LayoutOptionCheckbox
                field="show_stroke_numbers"
                label="Hiện số thứ tự nét 1, 2, 3..."
                defaultChecked={true}
                className="flex items-center gap-2 cursor-pointer select-none pl-3 border-l-2 border-primary/30"
                {...checkboxProps}
              />
            )}
          </>
        )}
        <LayoutOptionCheckbox field="show_reading" label="Hiện Âm đọc" defaultChecked={false} {...checkboxProps} />
        <LayoutOptionCheckbox field="show_meaning" label="Hiện Ý nghĩa" defaultChecked={false} {...checkboxProps} />
        {(isStrokeTemplate || isStepTemplate) && (
          <LayoutOptionCheckbox field="show_source_word" label="Hiện Từ ví dụ" defaultChecked={false} {...checkboxProps} />
        )}
      </div>
    </div>
  )
}

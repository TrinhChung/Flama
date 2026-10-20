import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { WorksheetLayoutOptions } from '../../../types'
import { OptionPill, OptionTile } from '../controls/LayoutOptionControls'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

const CONTENT_MODES: { id: NonNullable<WorksheetLayoutOptions['content_mode']>; label: string }[] = [
  { id: 'blank', label: 'Trang trắng (Tập viết tay)' },
  { id: 'text', label: 'Điền văn bản mẫu' },
  { id: 'trace', label: 'Tô chữ nét mờ' },
]
const BOX_STYLES: { id: NonNullable<WorksheetLayoutOptions['box_style']>; label: string }[] = [
  { id: 'square', label: 'Ô trơn (Plain)' },
  { id: 'cross', label: 'Chữ thập (+)' },
  { id: 'diagonal', label: 'Hoa thị (*)' },
]
const GRID_COLORS = [
  { color: '#475569', label: 'Xám than (Chuẩn)' },
  { color: '#0d9488', label: 'Xanh ngọc' },
  { color: '#e11d48', label: 'Đỏ đất' },
]
const PAGE_COUNTS = [1, 2, 3, 4, 5]
const SPACER_HEIGHTS = [6, 8, 10, 12, 14]

/** Genkō yōshi / 作文纸 essay grid controls. */
export function GenkouyoushiConfig({
  layoutOptions,
  setLayoutOptions,
}: Pick<StudioLayoutTabProps, 'layoutOptions' | 'setLayoutOptions'>) {
  return (
    <div className="space-y-3 pt-3 border-t border-border/60">
      <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
        Tuỳ biến Lưới bài văn Genkō Yōshi / 作文纸 (400 ô)
      </h4>

      {/* Content Mode Selection */}
      <div className="space-y-2 bg-muted/20 p-3 rounded-xl border border-border/80">
        <Label className="text-xs font-bold text-foreground">Chế độ nội dung trang:</Label>
        <div className="grid grid-cols-3 gap-1.5">
          {CONTENT_MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  content_mode: m.id,
                }))
              }
              className={`py-2 px-1.5 rounded-lg border text-center text-xs font-medium transition-all ${
                (layoutOptions.content_mode || 'blank') === m.id
                  ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Text Input when mode is text or trace */}
        {(layoutOptions.content_mode === 'text' || layoutOptions.content_mode === 'trace') && (
          <div className="space-y-1 pt-2">
            <Label className="text-xs font-semibold">Nhập nội dung bài văn mẫu:</Label>
            <textarea
              rows={4}
              value={layoutOptions.custom_text || ''}
              onChange={(e) =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  custom_text: e.target.value,
                }))
              }
              className="w-full text-xs p-2 rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary font-sans leading-relaxed"
              placeholder="Dán hoặc gõ đoạn văn bản tại đây (tự động phân bổ vào từng ô vuông 20x20)..."
            />
            <p className="text-[10px] text-muted-foreground">
              Để trống nếu muốn hệ thống tự động lấy nội dung từ các thẻ học trong bộ.
            </p>
          </div>
        )}

        {/* Page count for sheets */}
        <div className="space-y-1 pt-2 border-t border-border/50">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-semibold">Số trang in:</Label>
            <span className="text-xs font-bold text-primary">
              {layoutOptions.essay_page_count ?? 1} trang
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            {PAGE_COUNTS.map((cnt) => (
              <OptionPill
                key={cnt}
                active={(layoutOptions.essay_page_count ?? 1) === cnt}
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    essay_page_count: cnt,
                  }))
                }
                className="flex-1 h-7.5 text-xs"
              >
                {cnt} trang
              </OptionPill>
            ))}
          </div>
        </div>
      </div>

      {/* Grid Specifications */}
      <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
        <Label className="text-xs font-bold text-foreground">Khổ ô & Quy cách:</Label>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() =>
              setLayoutOptions((prev) => ({
                ...prev,
                grid_columns: 20,
                grid_rows: 20,
                footer_brand_label: 'Flama (400格)',
              }))
            }
            className={`p-2 rounded-lg border text-left text-xs transition-all ${
              (layoutOptions.grid_columns ?? 20) === 20 && (layoutOptions.grid_rows ?? 20) === 20
                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
            }`}
          >
            <div className="font-bold">400 ô (20 × 20)</div>
            <div className="text-[10px] text-muted-foreground font-normal">Chuẩn giấy làm văn tiêu chuẩn</div>
          </button>
          <button
            type="button"
            onClick={() =>
              setLayoutOptions((prev) => ({
                ...prev,
                grid_columns: 20,
                grid_rows: 10,
                footer_brand_label: 'Flama (200格)',
              }))
            }
            className={`p-2 rounded-lg border text-left text-xs transition-all ${
              (layoutOptions.grid_rows ?? 20) === 10
                ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
            }`}
          >
            <div className="font-bold">200 ô (20 × 10)</div>
            <div className="text-[10px] text-muted-foreground font-normal">Khổ thưa thoáng cho người mới</div>
          </button>
        </div>

        {/* Box Style */}
        <div className="space-y-1 pt-1.5 border-t border-border/50">
          <Label className="text-xs font-semibold">Kiểu ô kẻ:</Label>
          <div className="grid grid-cols-3 gap-1.5">
            {BOX_STYLES.map((bs) => (
              <OptionTile
                key={bs.id}
                active={(layoutOptions.box_style || 'square') === bs.id}
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    box_style: bs.id,
                  }))
                }
                className="py-1.5 px-2 rounded-lg border text-center text-xs font-medium transition-all"
              >
                {bs.label}
              </OptionTile>
            ))}
          </div>
        </div>

        {/* Grid Line Color */}
        <div className="space-y-1 pt-1.5 border-t border-border/50">
          <Label className="text-xs font-semibold">Màu mực đường kẻ:</Label>
          <div className="grid grid-cols-3 gap-1.5">
            {GRID_COLORS.map((c) => (
              <OptionTile
                key={c.color}
                active={(layoutOptions.grid_color || '#475569') === c.color}
                onClick={() =>
                  setLayoutOptions((prev) => ({
                    ...prev,
                    grid_color: c.color,
                  }))
                }
                className="flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border text-xs font-medium transition-all"
              >
                <span className="size-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                <span>{c.label}</span>
              </OptionTile>
            ))}
          </div>
        </div>

        {/* Spacer Band Between Rows */}
        <div className="space-y-2 pt-1.5 border-t border-border/50">
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={layoutOptions.has_spacer_band !== false}
              onChange={(e) =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  has_spacer_band: e.target.checked,
                }))
              }
              className="rounded text-primary size-4"
            />
            <div>
              <div className="text-xs font-bold text-foreground">
                Dải đệm ngang giữa các hàng (Spacer Band)
              </div>
              <p className="text-[10px] text-muted-foreground">
                Đúng chuẩn giấy luyện văn 作文纸 (dải đệm trống không kẻ dọc giữa các dòng ô)
              </p>
            </div>
          </label>

          {layoutOptions.has_spacer_band !== false && (
            <div className="flex items-center gap-1.5 pl-6">
              <Label className="text-[11px] text-muted-foreground shrink-0">Độ cao đệm:</Label>
              {SPACER_HEIGHTS.map((h) => (
                <Button
                  key={h}
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      spacer_height: h,
                    }))
                  }
                  className={`flex-1 h-6 text-[10px] px-1 ${
                    (layoutOptions.spacer_height ?? 10) === h
                      ? 'bg-primary text-primary-foreground font-bold border-primary'
                      : 'bg-background hover:bg-muted text-muted-foreground'
                  }`}
                >
                  {h}px
                </Button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

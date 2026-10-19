import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

export function EssayWritingConfig({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
}: Pick<
  StudioLayoutTabProps,
  'currentTemplate' | 'layoutOptions' | 'setLayoutOptions'
>) {
  if (!currentTemplate) return null

  return (
    <>
                      {/* SENTENCE WRITING OPTIONS */}
                      {currentTemplate.id === 'sentence_writing' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Mẫu câu & Dòng kẻ viết tay
                          </h4>
                          <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                            {/* Exercise prompt for sentence writing */}
                            <div className="space-y-1.5">
                              <Label className="text-xs font-semibold">Đề bài / Yêu cầu của bài tập (Đầu trang):</Label>
                              <Input
                                value={
                                  layoutOptions.exercise_prompt ??
                                  'Dịch các câu sau sang tiếng Việt hoặc phát triển thành đoạn văn:'
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    exercise_prompt: e.target.value,
                                  }))
                                }
                                className="h-8 text-xs font-medium"
                                placeholder="Ví dụ: Dịch câu sang tiếng Việt, Viết phát triển thành đoạn văn..."
                              />
                              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                {[
                                  'Dịch các câu sau sang tiếng Việt:',
                                  'Viết lại mỗi câu 3 lần:',
                                  'Đặt câu mới sử dụng cấu trúc mẫu:',
                                  'Nghe & chép chính tả (Dictation):',
                                ].map((pText) => (
                                  <button
                                    key={pText}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        exercise_prompt: pText,
                                      }))
                                    }
                                    className="text-[10px] px-2 py-0.5 rounded-md border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    {pText}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Number of writing lines */}
                            <div className="space-y-1 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số dòng kẻ viết tay mỗi câu:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.writing_lines_count ?? 3} dòng
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                                  <Button
                                    key={n}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: n,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.writing_lines_count ?? 3) === n
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {n}
                                  </Button>
                                ))}
                              </div>
                              <p className="text-[10px] text-muted-foreground">
                                Tăng số dòng nếu yêu cầu học sinh viết cả đoạn văn hoặc dịch câu dài.
                              </p>
                            </div>

                            {/* Writing line style */}
                            <div className="space-y-1 pt-1">
                              <Label className="text-xs font-semibold">Kiểu đường kẻ:</Label>
                              <div className="grid grid-cols-2 gap-1.5">
                                {[
                                  { id: 'dashed', label: '--- Nét đứt (Dashed)' },
                                  { id: 'solid', label: '─── Nét liền (Solid)' },
                                ].map((st) => (
                                  <button
                                    key={st.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_line_style: st.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.writing_line_style || 'dashed') === st.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {st.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Toggles for sentence parts */}
                            <div className="space-y-1.5 pt-1 text-xs">
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_sentence !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_sentence: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện câu mẫu</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_reading !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_reading: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện cách đọc / Furigana</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_sample_meaning !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_sample_meaning: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện ý nghĩa (Tắt để bắt học sinh tự dịch)</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* GRAMMAR PRACTICE OPTIONS */}
                      {currentTemplate.id === 'grammar_practice' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bài tập Ngữ pháp & Đề bài
                          </h4>
                          <div className="space-y-2.5 bg-muted/20 p-3 rounded-xl border border-border/80">
                            {/* Exercise prompt */}
                            <div className="space-y-1.5">
                              <Label className="text-xs font-semibold">Đề bài / Yêu cầu của giáo viên:</Label>
                              <Input
                                value={
                                  layoutOptions.exercise_prompt ??
                                  'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:'
                                }
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    exercise_prompt: e.target.value,
                                  }))
                                }
                                className="h-8 text-xs font-medium"
                                placeholder="Ví dụ: Đặt 2 câu với cấu trúc trên, Dịch sang tiếng Nhật..."
                              />
                              <div className="flex items-center gap-1 flex-wrap pt-0.5">
                                {[
                                  'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:',
                                  'Viết đoạn văn ngắn (3-4 câu) áp dụng ngữ pháp:',
                                  'Dịch các câu ví dụ sang tiếng Việt:',
                                  'Tìm lỗi sai và viết lại câu đúng:',
                                ].map((pText) => (
                                  <button
                                    key={pText}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        exercise_prompt: pText,
                                      }))
                                    }
                                    className="text-[10px] px-2 py-0.5 rounded-md border border-border bg-background hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                  >
                                    {pText}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Number of writing lines */}
                            <div className="space-y-1 pt-1">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số dòng kẻ viết bài mỗi mục:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.writing_lines_count ?? 3} dòng
                                </span>
                              </div>
                              <div className="flex items-center gap-1">
                                {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                                  <Button
                                    key={n}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_lines_count: n,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.writing_lines_count ?? 3) === n
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {n}
                                  </Button>
                                ))}
                              </div>
                            </div>

                            {/* Writing line style */}
                            <div className="space-y-1 pt-1">
                              <Label className="text-xs font-semibold">Kiểu đường kẻ:</Label>
                              <div className="grid grid-cols-2 gap-1.5">
                                {[
                                  { id: 'dashed', label: '--- Nét đứt (Dashed)' },
                                  { id: 'solid', label: '─── Nét liền (Solid)' },
                                ].map((st) => (
                                  <button
                                    key={st.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        writing_line_style: st.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.writing_line_style || 'dashed') === st.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {st.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Toggles for explanation & example */}
                            <div className="space-y-1.5 pt-1 text-xs">
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_explanation !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_explanation: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện giải thích cách dùng / ý nghĩa</span>
                              </label>
                              <label className="flex items-center gap-2 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_example_hint !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_example_hint: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-3.5"
                                />
                                <span>Hiện câu ví dụ mẫu gợi ý</span>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Genkouyoushi Essay Grid Controls */}
                      {currentTemplate.id === 'genkouyoushi' && (
                        <div className="space-y-3 pt-3 border-t border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Lưới bài văn Genkō Yōshi / 作文纸 (400 ô)
                          </h4>

                          {/* Content Mode Selection */}
                          <div className="space-y-2 bg-muted/20 p-3 rounded-xl border border-border/80">
                            <Label className="text-xs font-bold text-foreground">Chế độ nội dung trang:</Label>
                            <div className="grid grid-cols-3 gap-1.5">
                              {[
                                { id: 'blank', label: 'Trang trắng (Tập viết tay)' },
                                { id: 'text', label: 'Điền văn bản mẫu' },
                                { id: 'trace', label: 'Tô chữ nét mờ' },
                              ].map((m) => (
                                <button
                                  key={m.id}
                                  type="button"
                                  onClick={() =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      content_mode: m.id as any,
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
                                {[1, 2, 3, 4, 5].map((cnt) => (
                                  <Button
                                    key={cnt}
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        essay_page_count: cnt,
                                      }))
                                    }
                                    className={`flex-1 h-7.5 text-xs ${
                                      (layoutOptions.essay_page_count ?? 1) === cnt
                                        ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                        : 'bg-background hover:bg-muted text-muted-foreground'
                                    }`}
                                  >
                                    {cnt} trang
                                  </Button>
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
                                {[
                                  { id: 'square', label: 'Ô trơn (Plain)' },
                                  { id: 'cross', label: 'Chữ thập (+)' },
                                  { id: 'diagonal', label: 'Hoa thị (*)' },
                                ].map((bs) => (
                                  <button
                                    key={bs.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        box_style: bs.id as any,
                                      }))
                                    }
                                    className={`py-1.5 px-2 rounded-lg border text-center text-xs font-medium transition-all ${
                                      (layoutOptions.box_style || 'square') === bs.id
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    {bs.label}
                                  </button>
                                ))}
                              </div>
                            </div>

                            {/* Grid Line Color */}
                            <div className="space-y-1 pt-1.5 border-t border-border/50">
                              <Label className="text-xs font-semibold">Màu mực đường kẻ:</Label>
                              <div className="grid grid-cols-3 gap-1.5">
                                {[
                                  { color: '#475569', label: 'Xám than (Chuẩn)' },
                                  { color: '#0d9488', label: 'Xanh ngọc' },
                                  { color: '#e11d48', label: 'Đỏ đất' },
                                ].map((c) => (
                                  <button
                                    key={c.color}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        grid_color: c.color,
                                      }))
                                    }
                                    className={`flex items-center justify-center gap-1.5 py-1.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                                      (layoutOptions.grid_color || '#475569') === c.color
                                        ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                                        : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    <span className="size-2.5 rounded-full" style={{ backgroundColor: c.color }} />
                                    <span>{c.label}</span>
                                  </button>
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
                                  {[6, 8, 10, 12, 14].map((h) => (
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
                      )}
    </>
  )
}

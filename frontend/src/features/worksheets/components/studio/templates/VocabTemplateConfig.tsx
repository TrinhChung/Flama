import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import type { StudioLayoutTabProps } from '../StudioLayoutTab'

export function VocabTemplateConfig({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
}: Pick<
  StudioLayoutTabProps,
  'currentTemplate' | 'layoutOptions' | 'setLayoutOptions'
>) {
  if (!currentTemplate) return null

  const isLandscape = layoutOptions.orientation === 'landscape'

  return (
    <>
                      {/* VOCABULARY WRITING SPECIFIC CONTROLS */}
                      {currentTemplate.id === 'vocab_writing' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bảng Luyện viết Từ vựng
                          </h4>

                          {/* Practice Type: Boxes, Lines, Grid */}
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">Kiểu vùng luyện viết:</Label>
                            <div className="grid grid-cols-3 gap-1.5">
                              {[
                                { id: 'boxes', label: '🔲 Ô vuông liền', desc: 'Dải ô vuông đều nhau' },
                                { id: 'lines', label: '✍️ Dòng kẻ viết', desc: 'Đường kẻ đứt tự do' },
                                { id: 'grid', label: '田 Ô lưới chữ Hán', desc: 'Đường kẻ chữ thập (+)' },
                              ].map((pt) => {
                                const currentType = layoutOptions.practice_type || 'boxes'
                                const isSelected = currentType === pt.id
                                return (
                                  <button
                                    key={pt.id}
                                    type="button"
                                    onClick={() =>
                                      setLayoutOptions((prev) => ({
                                        ...prev,
                                        practice_type: pt.id as any,
                                      }))
                                    }
                                    className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                      isSelected
                                        ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                        : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                    }`}
                                  >
                                    <div className="truncate font-semibold">{pt.label}</div>
                                    <div className="text-[9.5px] text-muted-foreground font-normal line-clamp-1 mt-0.5">
                                      {pt.desc}
                                    </div>
                                  </button>
                                )
                              })}
                            </div>
                          </div>

                          {/* If boxes or grid: Practice Boxes Count Stepper & Quick Select */}
                          {layoutOptions.practice_type !== 'lines' && (
                            <div className="space-y-1.5 pt-1 border-t border-border/50">
                              <div className="flex items-center justify-between">
                                <Label className="text-xs font-semibold">Số ô luyện viết mỗi từ:</Label>
                                <span className="text-xs font-bold text-primary">
                                  {layoutOptions.practice_boxes_count ?? (isLandscape ? 10 : 6)} ô
                                </span>
                              </div>
                              <div className="grid grid-cols-5 gap-1">
                                {[4, 6, 8, 10, 12].map((cnt) => {
                                  const currentCnt = layoutOptions.practice_boxes_count ?? (isLandscape ? 10 : 6)
                                  return (
                                    <Button
                                      key={cnt}
                                      type="button"
                                      variant="outline"
                                      size="sm"
                                      onClick={() =>
                                        setLayoutOptions((prev) => ({
                                          ...prev,
                                          practice_boxes_count: cnt,
                                        }))
                                      }
                                      className={`h-7.5 text-xs ${
                                        currentCnt === cnt
                                          ? 'bg-primary text-primary-foreground font-bold border-primary shadow-2xs'
                                          : 'bg-card hover:bg-muted text-muted-foreground'
                                      }`}
                                    >
                                      {cnt} ô
                                    </Button>
                                  )
                                })}
                              </div>
                            </div>
                          )}

                          {/* Visible Columns Toggles: Reading & Meaning */}
                          <div className="space-y-2 pt-1.5 border-t border-border/50">
                            <Label className="text-xs font-semibold">Hiển thị các cột nội dung:</Label>
                            <div className="grid grid-cols-2 gap-2 text-xs">
                              <label className="flex items-center gap-2 p-2 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_reading !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_reading: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-4"
                                />
                                <div>
                                  <div className="font-semibold text-foreground">Cột Cách đọc</div>
                                  <div className="text-[10px] text-muted-foreground">Furigana / Kana / Pinyin</div>
                                </div>
                              </label>
                              <label className="flex items-center gap-2 p-2 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  checked={layoutOptions.show_meaning !== false}
                                  onChange={(e) =>
                                    setLayoutOptions((prev) => ({
                                      ...prev,
                                      show_meaning: e.target.checked,
                                    }))
                                  }
                                  className="rounded text-primary size-4"
                                />
                                <div>
                                  <div className="font-semibold text-foreground">Cột Ý nghĩa</div>
                                  <div className="text-[10px] text-muted-foreground">Dịch nghĩa tiếng Việt</div>
                                </div>
                              </label>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* VOCAB RECALL SPECIFIC CONTROLS */}
                      {currentTemplate.id === 'vocab_recall' && (
                        <div className="space-y-3 bg-muted/30 p-3.5 rounded-xl border border-border/60">
                          <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                            Tuỳ biến Bài tập Kiểm tra Trí nhớ (Recall & Cloze)
                          </h4>

                          {/* Answer Area Style */}
                          <div className="space-y-1.5">
                            <Label className="text-xs font-semibold">Kiểu vùng điền câu trả lời:</Label>
                            <div className="grid grid-cols-2 gap-2">
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    recall_answer_style: 'line',
                                    show_word_length_hint: false,
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  (layoutOptions.recall_answer_style || 'line') === 'line' && !layoutOptions.show_word_length_hint
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">✍️ Dòng kẻ nét đứt</div>
                                <div className="text-[10px] text-muted-foreground font-normal mt-0.5">
                                  Dòng kẻ sạch sẽ để học sinh tự do nhớ và viết
                                </div>
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    recall_answer_style: 'boxes',
                                    show_word_length_hint: true,
                                  }))
                                }
                                className={`p-2 rounded-lg border text-left text-xs transition-all ${
                                  layoutOptions.recall_answer_style === 'boxes' || layoutOptions.show_word_length_hint
                                    ? 'border-primary bg-primary/10 text-primary font-bold shadow-2xs'
                                    : 'border-border bg-card text-muted-foreground hover:bg-muted/50'
                                }`}
                              >
                                <div className="font-bold">🔲 Dải ô chữ cái (Gợi ý số ký tự)</div>
                                <div className="text-[10px] text-muted-foreground font-normal mt-0.5">
                                  Hiển thị số ô tương ứng độ dài từ cần điền
                                </div>
                              </button>
                            </div>
                          </div>

                          {/* Reading hint toggle */}
                          <div className="pt-1.5 border-t border-border/50">
                            <label className="flex items-center gap-2 p-2.5 rounded-lg border border-border/70 bg-card cursor-pointer select-none">
                              <input
                                type="checkbox"
                                checked={layoutOptions.show_reading_hint !== false}
                                onChange={(e) =>
                                  setLayoutOptions((prev) => ({
                                    ...prev,
                                    show_reading_hint: e.target.checked,
                                  }))
                                }
                                className="rounded text-primary size-4"
                              />
                              <div>
                                <div className="text-xs font-semibold text-foreground">
                                  Hiển thị gợi ý Cách đọc (Furigana / Kana)
                                </div>
                                <p className="text-[10px] text-muted-foreground">
                                  Tắt đi nếu muốn học viên phải tự nhớ toàn bộ từ chỉ dựa trên Nghĩa
                                </p>
                              </div>
                            </label>
                          </div>
                        </div>
                      )}
    </>
  )
}

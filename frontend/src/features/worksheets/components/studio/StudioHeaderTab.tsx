import { useTranslation } from 'react-i18next'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { DeckWorksheetMeta, WorksheetLayoutOptions } from '../../types'

export interface StudioHeaderTabProps {
  currentTemplate: DeckWorksheetMeta['templates'][0] | null
  layoutOptions: WorksheetLayoutOptions
  setLayoutOptions: React.Dispatch<React.SetStateAction<WorksheetLayoutOptions>>
}

export function StudioHeaderTab({
  currentTemplate,
  layoutOptions,
  setLayoutOptions,
}: StudioHeaderTabProps) {
  const { t } = useTranslation('worksheets')

  return (
    <div className="space-y-4 bg-card p-3.5 rounded-xl border border-border/70 shadow-xs">
      <div className="space-y-3">
        <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
          Tiêu đề & Đầu trang
        </h4>

        <div className="space-y-2.5">
          <div className="space-y-1">
            <Label className="text-xs font-semibold">
              {t('studio.header_tab.title_label', 'Tiêu đề bài tập')}
            </Label>
            <Input
              value={layoutOptions.header_title || ''}
              onChange={(e) =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  header_title: e.target.value,
                }))
              }
              className="h-8.5 text-xs"
              placeholder={t('studio.header_tab.title_placeholder', 'Ví dụ: JLPT N5 - Luyện viết chữ Hán')}
            />
          </div>

          <div className="space-y-1">
            <Label className="text-xs font-semibold">
              {t('studio.header_tab.subtitle_label', 'Phụ đề / Hướng dẫn nhỏ')}
            </Label>
            <Input
              value={layoutOptions.header_subtitle || ''}
              onChange={(e) =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  header_subtitle: e.target.value,
                }))
              }
              className="h-8.5 text-xs"
              placeholder="Luyện viết từ vựng và chữ Hán mỗi ngày"
            />
          </div>

          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-semibold">Đề bài / Yêu cầu bài tập (In ở đầu trang)</Label>
              {layoutOptions.exercise_prompt && (
                <button
                  type="button"
                  onClick={() =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      exercise_prompt: '',
                    }))
                  }
                  className="text-[10px] text-muted-foreground hover:text-rose-500 transition-colors"
                >
                  Xoá yêu cầu
                </button>
              )}
            </div>
            <Input
              value={layoutOptions.exercise_prompt || ''}
              onChange={(e) =>
                setLayoutOptions((prev) => ({
                  ...prev,
                  exercise_prompt: e.target.value,
                }))
              }
              className="h-8.5 text-xs font-medium"
              placeholder="Ví dụ: Hãy đặt 2 câu hoàn chỉnh với mỗi cấu trúc, Dịch các câu sau sang tiếng Việt..."
            />
            <p className="text-[10px] text-muted-foreground">
              Đề bài sẽ được in nổi bật trong khung ở đầu trang để học sinh nắm rõ yêu cầu làm bài.
            </p>
          </div>

          {/* Genkouyoushi specific header and footer controls */}
          {currentTemplate?.id === 'genkouyoushi' ? (
            <div className="space-y-3 pt-2 border-t border-border/60">
              <div className="space-y-1">
                <Label className="text-xs font-semibold">Khung thông tin học sinh:</Label>
                <div className="grid grid-cols-2 gap-1.5">
                  {[
                    { id: 'chinese', label: '班级 / 姓名 / 学号 / 分数' },
                    { id: 'vietnamese', label: 'Lớp / Họ tên / Mã số / Điểm' },
                    { id: 'japanese', label: 'クラス / 氏名 / 学籍番号 / 得点' },
                    { id: 'none', label: 'Ẩn khung học sinh' },
                  ].map((st) => (
                    <button
                      key={st.id}
                      type="button"
                      onClick={() =>
                        setLayoutOptions((prev) => ({
                          ...prev,
                          header_student_style: st.id as any,
                          show_student_info: st.id !== 'none',
                        }))
                      }
                      className={`p-2 rounded-lg border text-left text-xs transition-all ${
                        (layoutOptions.header_student_style || 'chinese') === st.id
                          ? 'border-primary bg-primary/10 text-primary font-bold shadow-xs'
                          : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                      }`}
                    >
                      {st.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-1 pt-1">
                <Label className="text-xs font-semibold">Vị trí in tiêu đề bài viết:</Label>
                <div className="grid grid-cols-3 gap-1.5">
                  {[
                    { id: 'first_row', label: 'Dòng 1 trong ô (Chuẩn)' },
                    { id: 'header', label: 'Đầu trang (Phía trên)' },
                    { id: 'none', label: 'Không in (Ô trống)' },
                  ].map((tp) => (
                    <button
                      key={tp.id}
                      type="button"
                      onClick={() =>
                        setLayoutOptions((prev) => ({
                          ...prev,
                          title_placement: tp.id as any,
                        }))
                      }
                      className={`py-1.5 px-2 rounded-lg border text-center text-xs font-medium transition-all ${
                        (layoutOptions.title_placement || 'none') === tp.id
                          ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                          : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                      }`}
                    >
                      {tp.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-border/60">
                <h4 className="text-xs font-bold text-foreground uppercase tracking-wider">
                  Chân trang & Định dạng ngày
                </h4>
                <div className="space-y-1">
                  <Label className="text-xs font-semibold">Nhãn chân trang góc trái:</Label>
                  <Input
                    value={layoutOptions.footer_brand_label || 'Flama (400格)'}
                    onChange={(e) =>
                      setLayoutOptions((prev) => ({
                        ...prev,
                        footer_brand_label: e.target.value,
                      }))
                    }
                    className="h-8.5 text-xs"
                    placeholder="Ví dụ: Flama (400格), 书行文创出品 (400格)..."
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs font-semibold">Định dạng ngày góc phải:</Label>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { id: 'chinese', label: '年  月  日' },
                      { id: 'vietnamese', label: 'Ngày ... Tháng ...' },
                      { id: 'none', label: 'Ẩn ngày' },
                    ].map((df) => (
                      <button
                        key={df.id}
                        type="button"
                        onClick={() =>
                          setLayoutOptions((prev) => ({
                            ...prev,
                            footer_date_format: df.id as any,
                          }))
                        }
                        className={`py-1.5 px-2 rounded-lg border text-center text-xs font-medium transition-all ${
                          (layoutOptions.footer_date_format || 'chinese') === df.id
                            ? 'border-primary bg-primary/5 text-foreground font-bold shadow-2xs'
                            : 'border-border bg-background text-muted-foreground hover:bg-muted/50'
                        }`}
                      >
                        {df.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-1.5 pt-1 text-xs">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={layoutOptions.show_student_info !== false}
                  onChange={(e) =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      show_student_info: e.target.checked,
                    }))
                  }
                  className="rounded text-primary size-3.5"
                />
                <span>{t('studio.header_tab.student_info', 'Hiện dòng Họ tên')}</span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={layoutOptions.show_date !== false}
                  onChange={(e) =>
                    setLayoutOptions((prev) => ({
                      ...prev,
                      show_date: e.target.checked,
                    }))
                  }
                  className="rounded text-primary size-3.5"
                />
                <span>{t('studio.header_tab.date_info', 'Hiện dòng Ngày tháng')}</span>
              </label>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

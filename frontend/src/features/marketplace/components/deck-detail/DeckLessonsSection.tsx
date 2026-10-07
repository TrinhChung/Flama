import { BookOpen, Layers, Search } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useTranslation } from 'react-i18next'

interface LessonItem {
  id: number
  name: string
  parent_id: number | null
  depth: number
  is_root: boolean
  direct_note_count: number
  direct_card_count: number
  note_count: number
  card_count: number
  total_note_count: number
  total_card_count: number
  has_children: boolean
}

interface DeckLessonsSectionProps {
  lessons?: LessonItem[]
  lessonCount?: number
  noteCount?: number
  sampleLength: number
  lessonSearch: string
  setLessonSearch: (search: string) => void
  displayLessons: LessonItem[]
}

export function DeckLessonsSection({
  lessons,
  lessonCount,
  noteCount,
  sampleLength,
  lessonSearch,
  setLessonSearch,
  displayLessons,
}: DeckLessonsSectionProps) {
  const { t, i18n } = useTranslation('marketplace')
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const totalNotes = (noteCount || sampleLength).toLocaleString(numberLocale)

  return (
    <Card className="border-border shadow-xs overflow-hidden rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
              <BookOpen className="size-5" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold flex flex-wrap items-center gap-2">
                <span>{t('detail.lessons_structure_title', 'Cấu trúc bài học & từ vựng')}</span>
                {lessonCount ? (
                  <Badge variant="secondary" className="text-xs font-bold rounded-md">
                    {lessonCount} {t('card.lesson_unit', 'bài')}
                  </Badge>
                ) : null}
                <Badge variant="outline" className="text-xs font-bold rounded-md text-primary border-primary/30">
                  {totalNotes} {t('card.note_unit', 'từ vựng')}
                </Badge>
              </CardTitle>
              <CardDescription className="text-xs">
                {t(
                  'detail.lessons_structure_desc',
                  'Chi tiết danh sách các bài học và số lượng từ vựng trong bộ thẻ này.'
                )}
              </CardDescription>
            </div>
          </div>

          {lessons && lessons.length > 3 ? (
            <div className="relative w-full sm:w-60">
              <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
              <Input
                placeholder={t('detail.lessons.search_placeholder', 'Tìm kiếm bài học...')}
                value={lessonSearch}
                onChange={(e) => setLessonSearch(e.target.value)}
                className="h-8 pl-8 text-xs rounded-lg"
              />
            </div>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="p-4 sm:p-5 pt-4 space-y-2.5">
        {displayLessons.length > 0 ? (
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {displayLessons.map((lesson, idx) => (
              <div
                key={lesson.id}
                className="flex items-center justify-between p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/30 transition-colors shadow-2xs gap-3"
                style={{ paddingLeft: `${Math.max(12, (lesson.depth || 0) * 16 + 12)}px` }}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary font-bold text-xs">
                    {lesson.depth > 0 ? '•' : idx + 1}
                  </div>
                  <span className="font-bold text-xs sm:text-sm text-foreground truncate">
                    {lesson.name}
                  </span>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Badge
                    variant="secondary"
                    className="font-bold text-xs px-2.5 py-0.5 rounded-md bg-primary/10 text-primary hover:bg-primary/15"
                  >
                    <Layers className="mr-1 size-3" />
                    {lesson.note_count.toLocaleString(numberLocale)} {t('card.note_unit', 'từ')}
                  </Badge>
                  {lesson.card_count && lesson.card_count !== lesson.note_count ? (
                    <Badge variant="outline" className="text-xs font-semibold text-muted-foreground rounded-md">
                      {lesson.card_count.toLocaleString(numberLocale)} {t('card.card_unit', 'thẻ')}
                    </Badge>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : lessonSearch ? (
          <div className="text-center py-6 text-xs text-muted-foreground">
            {t('detail.lessons.not_found_query', {
              query: lessonSearch,
              defaultValue: `Không tìm thấy bài học nào phù hợp với từ khóa "${lessonSearch}".`,
            })}
          </div>
        ) : (
          <div className="flex items-center justify-between p-4 rounded-xl border border-border/80 bg-muted/20 text-xs">
            <span className="font-semibold text-foreground">
              {t('detail.lessons.single_lesson_summary', '1 bài học tổng hợp')}
            </span>
            <Badge variant="secondary" className="font-bold text-xs">
              {totalNotes} {t('card.note_unit', 'từ vựng')}
            </Badge>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

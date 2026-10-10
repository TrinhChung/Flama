import { ChevronLeft, ChevronRight, ExternalLink, Eye, Layers, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { CardDisplay, CardSideToggle } from '@/entities/flashcard'
import { EmptyState } from '@/shared/components/PageState'
import { useTranslation } from 'react-i18next'

interface TemplateItem {
  id: string
  name: string
  position?: number
}

interface SourceNoteType {
  id: string
  title?: string
  name?: string
  templates?: TemplateItem[]
}

interface TestSample {
  note_id?: string
  word?: string
  reading?: string
  meaning?: string
}

interface DeckCardPreviewSectionProps {
  id: string
  sourceNoteType?: SourceNoteType | null
  templates: TemplateItem[]
  selectedTemplateId: string
  setSelectedTemplateId: (id: string) => void
  previewSide: 'front' | 'back'
  setPreviewSide: (side: 'front' | 'back') => void
  samples: TestSample[]
  activeSampleIndex: number
  setActiveSampleIndex: (index: number) => void
  handlePrevSample: () => void
  handleNextSample: () => void
  currentSample: TestSample | null
  previewQuery: {
    isPending: boolean
    data?: {
      front_html?: string
      back_html?: string
      front_renderer_payload?: unknown
      back_renderer_payload?: unknown
    }
  }
}

export function DeckCardPreviewSection({
  id,
  sourceNoteType,
  templates,
  selectedTemplateId,
  setSelectedTemplateId,
  previewSide,
  setPreviewSide,
  samples,
  activeSampleIndex,
  setActiveSampleIndex,
  handlePrevSample,
  handleNextSample,
  currentSample,
  previewQuery,
}: DeckCardPreviewSectionProps) {
  const { t } = useTranslation('marketplace')

  return (
    <Card className="border-border shadow-xs overflow-hidden rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2.5 rounded-xl bg-primary/10 text-primary">
              <Eye className="size-5" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">
                {t('detail.preview.title', 'Xem trước thẻ (Live Previewer)')}
              </CardTitle>
              <CardDescription className="text-xs">
                {t('detail.preview.subtitle', 'Mô phỏng hiển thị Anki Flashcard thực tế')}
              </CardDescription>
            </div>
          </div>

          {/* Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {sourceNoteType ? (
              <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 text-xs font-semibold rounded-lg">
                <Link to={`/marketplace/note-types/${sourceNoteType.id}`}>
                  <ExternalLink className="mr-1 size-3.5" />
                  {sourceNoteType.title || sourceNoteType.name || t('detail.notetype_source', 'NoteType nguồn')}
                </Link>
              </Button>
            ) : null}

            {templates.length > 1 ? (
              <NativeSelect
                value={selectedTemplateId}
                onChange={(e) => setSelectedTemplateId(e.target.value)}
                className="h-8 sm:h-9 text-xs font-medium w-36 rounded-lg"
              >
                {templates.map((tmpl) => (
                  <NativeSelectOption key={tmpl.id} value={tmpl.id}>
                    {tmpl.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            ) : null}

            <CardSideToggle
              size="default"
              showFlipIcon={false}
              side={previewSide}
              onSideChange={setPreviewSide}
              frontLabel={t('detail.preview.tab_front', 'Mặt trước')}
              backLabel={t('detail.preview.tab_back', 'Mặt sau')}
            />

            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-3 text-xs font-semibold rounded-lg"
                onClick={handlePrevSample}
                disabled={!samples.length}
                title={t('common.prev', 'Trước')}
              >
                <ChevronLeft className="size-3.5 mr-0.5" />
                {t('common.prev', 'Trước')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-8 px-3 text-xs font-semibold rounded-lg"
                onClick={handleNextSample}
                disabled={!samples.length}
                title={t('common.next', 'Sau')}
              >
                {t('common.next', 'Sau')}
                <ChevronRight className="size-3.5 ml-0.5" />
              </Button>
            </div>
          </div>
        </div>

        {/* Status Indicator */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2.5 text-xs text-muted-foreground border-t border-border/50">
          <div className="font-semibold text-foreground flex items-center gap-1.5">
            <Layers className="size-3.5 text-muted-foreground" />
            <span>
              {samples.length > 0
                ? `${t('detail.preview.sample_prefix', 'Mẫu')} ${activeSampleIndex + 1}/${samples.length}: ${(currentSample?.word || '').trim() || t('detail.preview.sample_word_default', 'Từ mẫu')} ${currentSample?.reading ? `(${currentSample.reading})` : ''}`
                : t('detail.preview.empty_preview', 'Chưa có từ mẫu')}
            </span>
          </div>
          {sourceNoteType ? (
            <span className="text-xs">
              NoteType: <strong className="text-foreground">{sourceNoteType.title || sourceNoteType.name}</strong>
            </span>
          ) : null}
        </div>
      </CardHeader>

      {/* Quick Word Select Chips with Smooth Horizontal Scroll */}
      {samples.length > 0 ? (
        <div className="p-3 sm:p-3.5 bg-muted/10 border-b border-border/60">
          <div className="text-xs font-semibold text-muted-foreground mb-1.5 flex items-center justify-between">
            <span>{t('detail.preview.quick_select', 'Chọn nhanh từ mẫu:')}</span>
            <span className="text-[11px] font-normal text-muted-foreground">
              ({samples.length} {t('detail.preview.samples_count_unit', 'mẫu')})
            </span>
          </div>
          <div
            className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none touch-pan-x overscroll-x-contain"
            style={{ WebkitOverflowScrolling: 'touch' }}
          >
            {samples.map((sample, idx) => {
              const isSelected = idx === activeSampleIndex
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setActiveSampleIndex(idx)}
                  className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-primary text-primary-foreground border-primary shadow-xs'
                      : 'bg-card text-foreground hover:bg-muted border-border/80'
                  }`}
                >
                  <span>{sample.word || `${t('detail.preview.word_hash', 'Từ #')}${idx + 1}`}</span>
                  {sample.reading ? (
                    <span className={`text-[10px] ${isSelected ? 'opacity-90' : 'text-muted-foreground'}`}>
                      ({sample.reading})
                    </span>
                  ) : null}
                </button>
              )
            })}
          </div>
        </div>
      ) : null}

      <CardContent className="p-4 sm:p-5 bg-muted/30">
        <div className="h-[clamp(20rem,50vh,32rem)] min-h-[250px] w-full overflow-hidden rounded-2xl border border-border bg-card shadow-xs">
          {previewQuery.isPending ? (
            <div className="flex h-full flex-col items-center justify-center p-8 space-y-2 text-muted-foreground">
              <Loader2 className="size-6 animate-spin text-primary" />
              <span className="text-xs font-medium">
                {t('detail.preview.loading', 'Đang tải bản xem trước thẻ...')}
              </span>
            </div>
          ) : previewQuery.data ? (
            <CardDisplay
              cardId={`preview-${id}`}
              noteId={currentSample?.note_id}
              side={previewSide}
              frontPayload={previewQuery.data.front_renderer_payload}
              backPayload={previewQuery.data.back_renderer_payload}
              frontHtml={previewQuery.data.front_html}
              backHtml={previewQuery.data.back_html}
              scope="shared_deck_preview"
              scopeId={id}
            />
          ) : (
            <EmptyState
              title={t('detail.preview.empty_title', 'Chưa có xem trước')}
              description={t('detail.preview.empty_desc', 'Deck này chưa cấu hình template hoặc không có thẻ mẫu.')}
            />
          )}
        </div>
      </CardContent>
    </Card>
  )
}

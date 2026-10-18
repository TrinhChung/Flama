import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  CheckCircle2,
  FileEdit,
  LayoutGrid,
  Printer,
  Sparkles,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LazyDeckWorksheetModal } from '../components/LazyDeckWorksheetModal'

export function WorksheetsPage() {
  const { t } = useTranslation('worksheets')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const paramDeckId = searchParams.get('deckId') || searchParams.get('deck_id')
  const paramDeckName = searchParams.get('deckName') || searchParams.get('deck_name')
  const initialDeckId = useMemo(() => {
    if (!paramDeckId) return null
    const parsed = Number(paramDeckId)
    return Number.isFinite(parsed) ? parsed : null
  }, [paramDeckId])
  const [isStudioOpen, setIsStudioOpen] = useState<boolean>(true)

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border/60 pb-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="size-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shadow-xs">
              <Printer className="size-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                  {t('page.title')}
                </h1>
                <Badge
                  variant="outline"
                  className="text-[10px] bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 font-semibold"
                >
                  {t('page.badge_standalone')}
                </Badge>
              </div>
              <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
                {t('page.description')}
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/dashboard')}
            className="h-9 gap-1.5 text-xs font-semibold rounded-lg"
          >
            <ArrowLeft className="size-3.5" />
            <span>{t('page.back_button')}</span>
          </Button>
          <Button
            size="sm"
            onClick={() => setIsStudioOpen(true)}
            className="h-9 gap-1.5 text-xs font-bold rounded-lg shadow-sm"
          >
            <Sparkles className="size-3.5" />
            <span>{t('page.open_studio')}</span>
          </Button>
        </div>
      </div>

      {/* Feature Highlights Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-rose-500/10 text-rose-600 dark:text-rose-400 flex items-center justify-center mb-1">
              <FileEdit className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">
              {t('page.cards.genkouyoushi.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('page.cards.genkouyoushi.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.genkouyoushi.f1')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.genkouyoushi.f2')}</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              {t('page.cards.genkouyoushi.action')}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center mb-1">
              <LayoutGrid className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">
              {t('page.cards.kanji_grid.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('page.cards.kanji_grid.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.kanji_grid.f1')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.kanji_grid.f2')}</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              {t('page.cards.kanji_grid.action')}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/70 hover:border-primary/50 transition-all hover:shadow-xs">
          <CardHeader className="pb-2">
            <div className="size-8 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-1">
              <Printer className="size-4" />
            </div>
            <CardTitle className="text-sm font-bold">
              {t('page.cards.pdf_print.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('page.cards.pdf_print.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="text-xs text-muted-foreground space-y-1.5 pt-1 border-t border-border/40">
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.pdf_print.f1')}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <CheckCircle2 className="size-3.5 text-emerald-600 shrink-0" />
              <span>{t('page.cards.pdf_print.f2')}</span>
            </div>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsStudioOpen(true)}
              className="w-full mt-2 h-7.5 text-xs font-semibold"
            >
              {t('page.cards.pdf_print.action')}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Standalone Live Studio Modal */}
      <LazyDeckWorksheetModal
        open={isStudioOpen}
        onOpenChange={setIsStudioOpen}
        deckId={initialDeckId}
        deckName={paramDeckName || undefined}
      />
    </div>
  )
}

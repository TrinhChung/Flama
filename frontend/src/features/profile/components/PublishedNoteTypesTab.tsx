import { useTranslation } from 'react-i18next'
import { DownloadCloud, Shapes, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { PublishedNoteType } from '../types/profile'

export function PublishedNoteTypesTab({
  noteTypes,
}: {
  noteTypes: PublishedNoteType[]
}) {
  const { t } = useTranslation('profile')

  if (!noteTypes || noteTypes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 p-8 sm:p-12 text-center">
        <Shapes className="size-8 sm:size-10 text-muted-foreground/40 mb-3" />
        <p className="text-sm font-semibold text-foreground">
          {t('published_note_types.empty_title')}
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm">
          {t('published_note_types.empty_description')}
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-3.5 sm:gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {noteTypes.map((nt) => (
        <Card
          key={nt.id}
          className="group relative flex flex-col overflow-hidden border-border/60 bg-card transition-all hover:border-primary/40 hover:shadow-md"
        >
          <CardContent className="flex flex-1 flex-col justify-between p-4 sm:p-5">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <Badge variant="outline" className="text-[11px]">
                  {t('published_note_types.type_badge')}
                </Badge>
                <span className="text-xs font-bold text-primary">
                  {nt.price_display}
                </span>
              </div>

              <h3 className="text-sm font-bold tracking-tight text-foreground line-clamp-2 group-hover:text-primary transition-colors">
                <Link to={`/marketplace/note-types/${nt.id}`}>
                  {nt.name}
                </Link>
              </h3>

              <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                {nt.description || t('published_note_types.default_description')}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-border/60 flex items-center justify-between text-xs text-muted-foreground">
              <div className="flex items-center gap-3">
                <span className="inline-flex items-center gap-1 font-semibold text-foreground">
                  <Star className="size-3.5 fill-amber-400 text-amber-500" />
                  {nt.rating_avg > 0 ? nt.rating_avg.toFixed(1) : t('published_note_types.rating_new')}
                </span>
                <span className="inline-flex items-center gap-1">
                  <DownloadCloud className="size-3.5" />
                  {nt.install_count}
                </span>
              </div>

              <Link
                to={`/marketplace/note-types/${nt.id}`}
                className="text-xs font-semibold text-primary hover:underline"
              >
                {t('published_note_types.view_details')}
              </Link>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

import { ArrowRight, Eye, Layers } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { TemplateLibrarySummary } from '@/entities/card-template'

export interface TemplateCardProps {
  template: TemplateLibrarySummary
}

export function TemplateCard({ template }: TemplateCardProps) {
  const { t } = useTranslation('card_templates')
  const detailUrl = `/card-templates/${encodeURIComponent(template.id)}`

  return (
    <Card className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl h-full">
      {/* Upper Info Block */}
      <div className="flex flex-col flex-1 space-y-2.5">
        {/* Badges Header Row */}
        <div className="flex items-center justify-between gap-1.5 flex-wrap">
          <div className="flex items-center gap-1.5 flex-wrap">
            <Badge
              variant="secondary"
              className="px-2 py-0.5 text-xs font-semibold rounded-md gap-1"
            >
              <Layers className="size-3 text-primary" />
              {template.origin === 'market_copy'
                ? t('library.badge_received')
                : t('library.badge_mine')}
            </Badge>
            {template.archived_at && (
              <Badge
                variant="outline"
                className="px-2 py-0.5 text-xs font-semibold rounded-md border-amber-500/40 text-amber-600 dark:text-amber-400 bg-amber-500/10"
              >
                {t('library.badge_archived')}
              </Badge>
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-1 group-hover:text-primary transition-colors leading-snug">
          <Link
            to={detailUrl}
            className="hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            {template.name}
          </Link>
        </h3>

        {/* Description */}
        {template.description ? (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
            {template.description}
          </p>
        ) : (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground/60 italic font-normal">
            {t('library.no_desc')}
          </p>
        )}
      </div>

      {/* Card Bottom Block */}
      <div className="mt-4 pt-3 border-t border-border/60 space-y-3">
        {/* Usage Stats Row */}
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="truncate">
            {template.note_type_count
              ? t('library.usage_note_types', { count: template.note_type_count })
              : t('library.usage_unused')}
            {template.application_count > template.note_type_count &&
              t('library.usage_attachments', { count: template.application_count })}
          </span>
        </div>

        {/* View Details Flama Button */}
        <Button
          size="sm"
          asChild
          className="w-full h-9 text-xs font-semibold rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs gap-1.5 transition-all"
        >
          <Link to={detailUrl}>
            <Eye className="size-3.5" />
            {t('library.btn_details')}
            <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      </div>
    </Card>
  )
}

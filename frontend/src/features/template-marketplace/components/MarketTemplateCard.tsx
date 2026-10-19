import { ArrowRight, Check, Download, Eye, SlidersHorizontal } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { MarketTemplateItem } from '../model/types'

const MAX_INPUT_CHIPS = 4

export function MarketTemplateCard({ item }: { item: MarketTemplateItem }) {
  const { t, i18n } = useTranslation('marketplace')
  const detailUrl = `/marketplace/templates/${encodeURIComponent(item.id)}`
  const authorName = item.author.username || t('card.community_author', { defaultValue: 'Cộng đồng Flama' })
  const extraInputs = item.inputs.length - MAX_INPUT_CHIPS

  return (
    <Card className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-md rounded-2xl">
      <div className="flex flex-col flex-1 space-y-3">
        <div className="flex items-center justify-between gap-1.5">
          <Badge variant="outline" className="px-2.5 py-0.5 text-xs font-semibold rounded-md truncate max-w-[65%] border bg-muted text-muted-foreground border-border/60">
            {item.primary_category || t('card.general_category', { defaultValue: 'Chung' })}
          </Badge>
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2.5 py-0.5 text-xs font-semibold ${
              item.pricing_mode === 'free'
                ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20'
                : 'bg-primary/10 text-primary border border-primary/20'
            }`}
          >
            {item.pricing_mode === 'free' ? t('card.free', { defaultValue: 'Miễn phí' }) : item.price_display}
          </span>
        </div>

        <h3 className="text-sm sm:text-base font-bold tracking-tight text-foreground line-clamp-2 leading-snug">
          <Link to={detailUrl} className="hover:text-primary hover:underline transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs">
            {item.name}
          </Link>
        </h3>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <div className="flex size-5 sm:size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20">
            {authorName.charAt(0).toUpperCase()}
          </div>
          <span className="font-medium text-foreground/80 truncate">{authorName}</span>
          {item.is_owner ? (
            <Badge variant="secondary" className="text-[10px] px-1.5 py-0 rounded-md">{t('templates.badge_owner')}</Badge>
          ) : null}
        </div>

        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
          {item.description || t('templates.no_desc')}
        </p>

        {item.inputs.length ? (
          <div className="flex flex-wrap gap-1.5" aria-label={t('templates.inputs_title')}>
            {item.inputs.slice(0, MAX_INPUT_CHIPS).map((input) => (
              <span key={input.key} className="rounded-md border border-border/70 bg-muted/40 px-2 py-0.5 text-[11px] font-medium text-foreground/80">
                {input.label}
              </span>
            ))}
            {extraInputs > 0 ? <span className="px-1 py-0.5 text-[11px] text-muted-foreground">+{extraInputs}</span> : null}
          </div>
        ) : null}
      </div>

      <div className="mt-4 pt-3.5 border-t border-border/60 space-y-3">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <SlidersHorizontal className="size-3.5 text-primary" />
            {t('templates.inputs_count', { count: item.input_count })}
          </span>
          <span className="inline-flex items-center gap-1">
            <Download className="size-3.5 text-primary" />
            <span className="tabular-nums">
              {item.install_count.toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')} {t('card.install_unit', { defaultValue: 'lượt' })}
            </span>
          </span>
        </div>

        <Button
          variant="outline"
          size="sm"
          asChild
          className="w-full h-9 text-xs font-semibold rounded-xl hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all"
        >
          <Link to={detailUrl}>
            {item.is_installed ? <Check className="mr-1.5 size-3.5 text-emerald-600" /> : <Eye className="mr-1.5 size-3.5" />}
            {item.is_installed ? t('templates.in_library') : t('card.btn_details', { defaultValue: 'Xem chi tiết' })}
            <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      </div>
    </Card>
  )
}

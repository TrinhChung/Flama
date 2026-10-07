import { ArrowRight, Download, Eye, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

interface SharedNoteTypeCardProps {
  item: {
    id: string
    title?: string
    name?: string
    description: string | null
    primary_category: string | null
    rating_avg: number
    rating_count?: number
    install_count: number
    price_display: string
    pricing_mode: string
    author: {
      username?: string
      account_name?: string
    } | null
  }
  index: number
  getCategoryBadgeStyle: (cat: string | null | undefined) => string
}

export function SharedNoteTypeCard({ item, index, getCategoryBadgeStyle }: SharedNoteTypeCardProps) {
  const { t } = useTranslation('marketplace')
  const itemTitle = item.name || item.title || t('card.no_title_notetype', { defaultValue: 'Mẫu thẻ không tên' })
  const detailUrl = `/marketplace/note-types/${item.id}`
  const authorName =
    item.author?.account_name || item.author?.username || t('card.community_author', { defaultValue: 'Cộng đồng Flama' })
  const authorInitial = authorName.charAt(0).toUpperCase()

  return (
    <Card
      data-tour={index === 0 ? 'market-card-first' : undefined}
      className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/40 hover:shadow-md rounded-2xl"
    >
      <div className="flex flex-col flex-1 space-y-3">
        <div className="flex items-center justify-between gap-1.5">
          <Badge
            variant="outline"
            className={`px-2.5 py-0.5 text-xs font-semibold rounded-md truncate max-w-[65%] border ${getCategoryBadgeStyle(
              item.primary_category,
            )}`}
          >
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
          <Link
            to={detailUrl}
            className="hover:text-primary hover:underline transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
          >
            {itemTitle}
          </Link>
        </h3>

        {item.author?.username ? (
          <Link
            to={`/profile/${item.author.username}`}
            className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-primary transition-colors group/author"
          >
            <div className="flex size-5 sm:size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20 group-hover/author:ring-primary">
              {authorInitial}
            </div>
            <span className="font-medium text-foreground/80 group-hover/author:text-primary truncate">
              {authorName}
            </span>
          </Link>
        ) : (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <div className="flex size-5 sm:size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-[10px] ring-1 ring-primary/20">
              {authorInitial}
            </div>
            <span className="font-medium text-foreground/80 truncate">
              {authorName}
            </span>
          </div>
        )}

        <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground font-normal">
          {item.description || t('card.no_desc_notetype', { defaultValue: 'Chưa có mô tả chi tiết cho loại thẻ này.' })}
        </p>
      </div>

      <div className="mt-4 pt-3.5 border-t border-border/60 space-y-3">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1 font-semibold text-foreground">
            <Star className="size-3.5 fill-amber-400 text-amber-500" />
            <span className="tabular-nums">
              {(item.rating_avg || 0).toFixed(1)}
              {item.rating_count ? (
                <span className="text-[11px] font-normal text-muted-foreground ml-0.5">
                  ({item.rating_count})
                </span>
              ) : null}
            </span>
          </span>

          <span className="inline-flex items-center gap-1">
            <Download className="size-3.5 text-primary" />
            <span className="tabular-nums">
              {(item.install_count || 0).toLocaleString('vi-VN')} {t('card.install_unit', { defaultValue: 'lượt' })}
            </span>
          </span>
        </div>

        <Button
          variant="outline"
          size="sm"
          asChild
          data-tour={index === 0 ? 'market-action-btn' : undefined}
          className="w-full h-9 text-xs font-semibold rounded-xl hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all"
        >
          <Link to={detailUrl}>
            <Eye className="mr-1.5 size-3.5" />
            {t('card.btn_details', { defaultValue: 'Xem chi tiết' })}
            <ArrowRight className="ml-1 size-3.5 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </Button>
      </div>
    </Card>
  )
}

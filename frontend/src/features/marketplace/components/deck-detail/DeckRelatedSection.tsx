import { Layers, Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from 'react-i18next'

interface MarketplaceItemMini {
  id: string
  title?: string
  name?: string
  price_display?: string
  rating_avg?: number
  author?: { username?: string } | null
  author_filter_token?: string
}

interface DeckRelatedSectionProps {
  relatedItems?: MarketplaceItemMini[]
}

export function DeckRelatedSection({ relatedItems }: DeckRelatedSectionProps) {
  const { t } = useTranslation('marketplace')

  if (!relatedItems || relatedItems.length === 0) return null

  return (
    <Card className="border-border shadow-xs rounded-2xl overflow-hidden">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-muted/20">
        <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2">
          <Layers className="size-4 text-primary" />
          <span>{t('detail.related.title', 'Bộ thẻ liên quan khác')}</span>
        </CardTitle>
        <CardDescription className="text-xs">
          {t(
            'detail.related.desc',
            'Khám phá thêm các bộ thẻ cùng chủ đề trên Flama Marketplace'
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
          {relatedItems.map((item) => (
            <Link
              key={item.id}
              to={`/marketplace/decks/${item.id}`}
              className="group block rounded-xl border border-border/80 bg-card p-3.5 hover:bg-muted/30 hover:border-primary/40 transition-all shadow-2xs"
            >
              <div className="font-bold text-xs sm:text-sm text-foreground group-hover:text-primary transition-colors line-clamp-1">
                {item.title || item.name || t('card.no_title', 'Bộ thẻ không tên')}
              </div>
              <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
                <span className="font-bold text-primary">
                  {item.price_display || t('card.free', 'Miễn phí')}
                </span>
                <span className="flex items-center gap-1 font-bold text-amber-500">
                  <Star className="size-3.5 fill-amber-400" />
                  {(item.rating_avg || 0).toFixed(1)}
                </span>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

import { ArrowRight } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DeckCard } from './DeckCard'

interface MarketplaceCuratedSectionProps {
  curatedSections: {
    majorSections: Array<{ category: string; items: any[] }>
    otherItems: any[]
  }
  getCategoryBadgeStyle: (categoryName: string | null | undefined) => string
  onSelectCategory: (cat: string) => void
}

export function MarketplaceCuratedSection({
  curatedSections,
  getCategoryBadgeStyle,
  onSelectCategory,
}: MarketplaceCuratedSectionProps) {
  return (
    <div className="space-y-8">
      {curatedSections.majorSections.map((section) => (
        <div key={section.category} className="space-y-3.5">
          <div className="flex items-center justify-between border-b border-border/50 pb-2">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={`px-2.5 py-0.5 text-xs font-bold rounded-md ${getCategoryBadgeStyle(
                  section.category,
                )}`}
              >
                {section.category}
              </Badge>
              <span className="text-xs font-semibold text-muted-foreground">
                ({section.items.length} bộ thẻ)
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSelectCategory(section.category)}
              className="h-8 text-xs font-semibold text-primary hover:text-primary hover:bg-primary/10 gap-1 rounded-lg cursor-pointer"
            >
              <span>Xem tất cả {section.category}</span>
              <ArrowRight className="size-3.5" />
            </Button>
          </div>
          <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {section.items.slice(0, 4).map((item, index) => (
              <DeckCard
                key={item.id}
                item={item}
                variant="marketplace"
                dataTour={index === 0 ? 'market-card-first' : undefined}
                actionDataTour={index === 0 ? 'market-action-btn' : undefined}
              />
            ))}
          </div>
        </div>
      ))}

      {curatedSections.otherItems.length > 0 && (
        <div className="space-y-3.5">
          <div className="flex items-center justify-between border-b border-border/50 pb-2">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-foreground">Học liệu & Chủ đề khác</h3>
              <span className="text-xs font-semibold text-muted-foreground">
                ({curatedSections.otherItems.length} bộ thẻ)
              </span>
            </div>
          </div>
          <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {curatedSections.otherItems.map((item) => (
              <DeckCard
                key={item.id}
                item={item}
                variant="marketplace"
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

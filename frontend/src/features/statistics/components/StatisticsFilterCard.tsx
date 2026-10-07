import '@/shared/config/i18n'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import type { StatisticsConfig, StatisticsFilters } from '../types'

function ChoiceTabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: Array<{ label: string; value: T }>
  onChange: (value: T) => void
}) {
  return (
    <Tabs value={value} onValueChange={(next) => onChange(next as T)}>
      <TabsList className="w-full h-9">
        {items.map((item) => (
          <TabsTrigger className="flex-1 text-xs font-medium min-h-[30px]" value={item.value} key={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}

interface StatisticsFilterCardProps {
  filters: StatisticsFilters
  decks: StatisticsConfig['decks']
  onUpdateFiltersAndUrl: (updater: (prev: StatisticsFilters) => StatisticsFilters) => void
  onSetFilters: (updater: (prev: StatisticsFilters) => StatisticsFilters) => void
}

export function StatisticsFilterCard({
  filters,
  decks,
  onUpdateFiltersAndUrl,
  onSetFilters,
}: StatisticsFilterCardProps) {
  const { t } = useTranslation('statistics')

  return (
    <Card className="shadow-xs border-border/80 bg-card">
      <CardContent className="grid gap-3.5 p-3.5 sm:gap-4 sm:p-5 sm:grid-cols-2 md:grid-cols-3">
        <div className="space-y-1.5">
          <Label className="text-xs font-semibold text-muted-foreground">
            {t('filters.scope_label')}
          </Label>
          <ChoiceTabs
            value={filters.scope}
            items={[
              { label: t('filters.scope_deck'), value: 'deck' },
              { label: t('filters.scope_collection'), value: 'collection' },
            ]}
            onChange={(scope) => onUpdateFiltersAndUrl((current) => ({ ...current, scope }))}
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="statistics-deck" className="text-xs font-semibold text-muted-foreground">
            {t('filters.deck_label')}
          </Label>
          <div className="flex items-center gap-2">
            <NativeSelect
              id="statistics-deck"
              className={cn(
                'flex-1 h-9 text-xs sm:text-sm',
                filters.scope === 'collection' && 'opacity-60 cursor-not-allowed',
              )}
              disabled={filters.scope === 'collection'}
              value={filters.scope === 'collection' ? '' : filters.deckId === null ? '' : String(filters.deckId)}
              onChange={(event) => {
                const nextId = event.currentTarget.value ? Number(event.currentTarget.value) : null
                onUpdateFiltersAndUrl((current) => ({ ...current, deckId: nextId }))
              }}
            >
              {filters.scope === 'collection' ? (
                <NativeSelectOption value="">{t('filters.entire_collection')}</NativeSelectOption>
              ) : (
                <>
                  <NativeSelectOption value="">{t('filters.select_deck')}</NativeSelectOption>
                  {decks.map((deck) => (
                    <NativeSelectOption key={deck.id} value={String(deck.id)}>
                      {deck.name}
                    </NativeSelectOption>
                  ))}
                </>
              )}
            </NativeSelect>

            {filters.scope === 'deck' && filters.deckId ? (
              <Button
                asChild
                size="sm"
                className="h-9 shrink-0 px-3 text-xs font-semibold bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
              >
                <Link to={`/study?deck_id=${filters.deckId}`}>
                  {t('filters.review_cta')}
                </Link>
              </Button>
            ) : filters.scope === 'collection' ? (
              <Button
                asChild
                size="sm"
                variant="outline"
                className="h-9 shrink-0 px-3 text-xs font-semibold hover:border-primary/50 hover:text-primary"
              >
                <Link to="/study">
                  {t('filters.review_cta')}
                </Link>
              </Button>
            ) : null}
          </div>
        </div>

        <div className="space-y-1.5 sm:col-span-2 md:col-span-1">
          <Label className="text-xs font-semibold text-muted-foreground">
            {t('filters.history_label')}
          </Label>
          <ChoiceTabs
            value={filters.historyRange}
            items={[
              { label: t('filters.history_12m'), value: '12m' },
              { label: t('filters.history_all'), value: 'all' },
            ]}
            onChange={(historyRange) => onSetFilters((current) => ({ ...current, historyRange }))}
          />
        </div>
      </CardContent>
    </Card>
  )
}

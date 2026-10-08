import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { BookOpen, Download, Loader2, Plus } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { RecommendedDeckItem } from '@/features/onboarding/types'

interface RecommendedDecksSectionProps {
  isDecksLoading: boolean
  recommendedDecks: RecommendedDeckItem[]
  installedDeckIds: Set<string>
  installingDeckId: string | null
  onInstallDeck: (deck: RecommendedDeckItem) => void
}

export function RecommendedDecksSection({
  isDecksLoading,
  recommendedDecks,
  installedDeckIds,
  installingDeckId,
  onInstallDeck,
}: RecommendedDecksSectionProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
          {t('study_goals.sections.library_decks_title')}
        </h3>
        <Button asChild variant="ghost" size="sm" className="text-xs font-medium text-muted-foreground hover:text-foreground">
          <Link to="/marketplace/decks">
            {t('study_goals.decks.marketplace_link')}
          </Link>
        </Button>
      </div>

      {isDecksLoading ? (
        <div className="flex items-center justify-center p-6 border rounded-xl bg-card">
          <Loader2 className="size-4 animate-spin text-primary mr-2" />
          <span className="text-xs text-muted-foreground">
            {t('study_goals.decks.loading')}
          </span>
        </div>
      ) : recommendedDecks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
          {recommendedDecks.map((deck) => {
            const isInstalled = installedDeckIds.has(deck.id)
            const isInstalling = installingDeckId === deck.id

            return (
              <div
                key={deck.id}
                className="flex flex-col justify-between p-3.5 rounded-xl border border-border/80 bg-card space-y-2.5"
              >
                <div className="space-y-1">
                  <h4 className="text-xs font-bold text-foreground line-clamp-1">{deck.title}</h4>
                  <p className="text-[11px] text-muted-foreground line-clamp-2">{deck.description}</p>
                </div>

                <div className="pt-2 border-t border-border/50 flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">
                    {t('study_goals.decks.card_count', { count: deck.card_count ?? 0 })}
                  </span>
                  {isInstalled ? (
                    <Badge variant="secondary" className="text-[10px]">
                      {t('study_goals.decks.installed_badge')}
                    </Badge>
                  ) : (
                    <Button
                      size="xs"
                      onClick={() => onInstallDeck(deck)}
                      disabled={isInstalling}
                      className="text-[11px] font-semibold h-7"
                    >
                      {isInstalling ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <>
                          <Download className="size-3 mr-1" /> {t('study_goals.decks.install_btn')}
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="p-5 rounded-xl border border-dashed border-border/80 bg-card/60 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h4 className="text-xs font-bold text-foreground">
              {t('study_goals.decks.empty_title')}
            </h4>
            <p className="text-xs text-muted-foreground max-w-xl">
              {t('study_goals.decks.empty_desc')}
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <Button asChild variant="outline" size="sm" className="h-8 text-xs font-semibold rounded-lg">
              <Link to="/guide/dashboard/deck-grouping">
                <BookOpen className="size-3.5 mr-1.5" />
                {t('study_goals.decks.guide_btn')}
              </Link>
            </Button>
            <Button asChild size="sm" className="h-8 text-xs font-semibold rounded-lg bg-primary text-primary-foreground">
              <Link to="/dashboard">
                <Plus className="size-3.5 mr-1.5" />
                {t('study_goals.decks.dashboard_btn')}
              </Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

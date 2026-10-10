import { useTranslation } from 'react-i18next'
import {
  Compass,
  Download,
  Plus as PlusLg,
  Search,
  Target,
  Upload,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { SUBJECT_OPTIONS } from '../constants'
import type { OnboardingPreferences } from '../types'

interface OnboardingHeroCardProps {
  preferences: OnboardingPreferences
  onOpenPreferences: () => void
  onOpenCreateDeck: () => void
  onStartTour: () => void
  hasDecks: boolean
}

export function OnboardingHeroCard({
  preferences,
  onOpenPreferences,
  onOpenCreateDeck,
  onStartTour,
  hasDecks,
}: OnboardingHeroCardProps) {
  const { t } = useTranslation('onboarding')
  const currentSubject =
    SUBJECT_OPTIONS.find((s) => s.id === preferences.targetSubject) || SUBJECT_OPTIONS[0]
  const currentLevel =
    currentSubject.levels.find((l) => l.id === preferences.frameworkLevel)?.label ||
    preferences.frameworkLevel.toUpperCase()

  return (
    <Card className="relative overflow-hidden border border-orange-500/20 bg-gradient-to-br from-orange-500/10 via-amber-500/5 to-transparent shadow-xs rounded-2xl">
      <div className="absolute top-0 right-0 -mr-10 -mt-10 size-48 rounded-full bg-gradient-to-br from-primary/10 to-orange-500/10 blur-2xl pointer-events-none" />

      <CardContent className="p-4 sm:p-5 relative space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                variant="default"
                className="text-[11px] font-bold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground shadow-xs px-2.5 py-0.5"
              >
                <Target className="size-3 mr-1" /> {t('hero_card.badge')}
              </Badge>
              <Badge variant="outline" className="text-[11px] font-semibold border-primary/30 text-primary">
                {currentSubject.flag} {currentSubject.title} • {currentLevel}
              </Badge>
              <Badge variant="secondary" className="text-[11px] font-semibold bg-muted text-muted-foreground">
                ⚡ {t('hero.daily_target_cards', { count: preferences.dailyNewCards })}
              </Badge>
            </div>
            <h2 className="text-base sm:text-lg font-bold text-foreground tracking-tight pt-0.5">
              {hasDecks
                ? t('hero_card.motivation_continue')
                : t('hero_card.motivation_start')}
            </h2>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={onOpenPreferences}
              className="h-8 px-3 text-xs font-semibold rounded-xl border-border/80 hover:border-primary/40 bg-card hover:bg-muted"
            >
              <Target className="size-3.5 mr-1.5 text-primary" />
              {t('hero_card.change_goal_button')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onStartTour}
              className="h-8 px-3 text-xs font-semibold rounded-xl border-border/80 hover:border-primary/40 bg-card hover:bg-muted"
            >
              <Compass className="size-3.5 mr-1.5 text-orange-500" />
              {t('hero_card.tour_button')}
            </Button>
          </div>
        </div>

        {/* Action Shortcuts Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
          <Button
            asChild
            variant="outline"
            size="sm"
            className="h-9 justify-start text-xs font-semibold rounded-xl border-border/70 bg-card/80 hover:bg-card hover:border-primary/50 text-foreground"
          >
            <Link to="/marketplace/decks">
              <Download className="size-3.5 mr-1.5 text-primary" />
              <span>{t('hero_card.deck_library_button')}</span>
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={onOpenCreateDeck}
            className="h-9 justify-start text-xs font-semibold rounded-xl border-border/70 bg-card/80 hover:bg-card hover:border-primary/50 text-foreground"
          >
            <PlusLg className="size-3.5 mr-1.5 text-orange-500" />
            <span>{t('hero_card.create_deck_button')}</span>
          </Button>

          <Button
            asChild
            variant="outline"
            size="sm"
            className="h-9 justify-start text-xs font-semibold rounded-xl border-border/70 bg-card/80 hover:bg-card hover:border-primary/50 text-foreground"
          >
            <Link to="/sync">
              <Upload className="size-3.5 mr-1.5 text-emerald-500" />
              <span>{t('hero_card.anki_sync_button')}</span>
            </Link>
          </Button>

          <Button
            asChild
            variant="outline"
            size="sm"
            className="h-9 justify-start text-xs font-semibold rounded-xl border-border/70 bg-card/80 hover:bg-card hover:border-primary/50 text-foreground"
          >
            <Link to="/browse">
              <Search className="size-3.5 mr-1.5 text-blue-500" />
              <span>{t('hero_card.browse_button')}</span>
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

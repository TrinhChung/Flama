import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'

interface DashboardSpotlightTourProps {
  isOpen: boolean
  onClose: () => void
  onComplete?: () => void
  hasDecks: boolean
}

export function DashboardSpotlightTour({
  isOpen,
  onClose,
  onComplete,
  hasDecks,
}: DashboardSpotlightTourProps) {
  const { t } = useTranslation('onboarding')

  const steps: TourStep[] = useMemo(() => {
    const list: TourStep[] = [
      {
        target: '[data-tour="dash-toolbar-nav"]',
        title: `🧭 ${t('tour.steps.header.title')}`,
        content: t('tour.steps.header.description'),
        placement: 'bottom',
      },
      {
        target: '[data-tour="dash-create-btn"]',
        title: `✨ ${t('tour.steps.create_deck.title')}`,
        content: t('tour.steps.create_deck.description'),
        placement: 'bottom',
      },
      {
        target: '[data-tour="dash-deck-board"]',
        title: `📊 ${t('tour.steps.deck_grid.title')}`,
        content: t('tour.steps.deck_grid.description'),
        placement: 'top',
      },
    ]

    if (hasDecks) {
      list.push(
        {
          target: '[data-tour="dash-deck-row-first"]',
          title: `🎴 ${t('tour.steps.deck_grid.title')}`,
          content: t('tour.steps.deck_grid.description'),
          placement: 'top',
        },
        {
          target: '[data-tour="dash-study-action"]',
          title: `⚡ ${t('tour.steps.quick_study.title')}`,
          content: t('tour.steps.quick_study.description'),
          placement: 'bottom',
        },
      )
    }

    list.push(
      {
        target: '[data-tour="dash-marketplace-link"]',
        title: `📚 ${t('tour.steps.anki_sync.title')}`,
        content: t('tour.steps.anki_sync.description'),
        placement: 'top',
      },
      {
        target: '[data-tour="dash-heatmap-section"]',
        title: `🔥 ${t('tour.steps.nav_stats.title')}`,
        content: t('tour.steps.nav_stats.description'),
        placement: 'top',
      },
      {
        target: '[data-tour="dash-tour-btn"]',
        title: `🎯 ${t('tour.steps.nav_settings.title')}`,
        content: t('tour.steps.nav_settings.description'),
        placement: 'bottom',
      },
    )

    return list
  }, [hasDecks, t])

  return (
    <SpotlightTour
      steps={steps}
      isOpen={isOpen}
      onClose={onClose}
      onComplete={onComplete}
    />
  )
}

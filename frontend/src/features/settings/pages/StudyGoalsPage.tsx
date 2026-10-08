import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { CheckCircle2, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
import { ContextHelpButton } from '@/features/guide'
import { useStudyGoals } from '../hooks/useStudyGoals'
import { StudyGoalSummaryCard } from '../components/study-goals/StudyGoalSummaryCard'
import { SubjectSelectSection } from '../components/study-goals/SubjectSelectSection'
import { LevelSelectSection } from '../components/study-goals/LevelSelectSection'
import { DailyTargetSection } from '../components/study-goals/DailyTargetSection'
import { StudyTimeSection } from '../components/study-goals/StudyTimeSection'
import { RecommendedDecksSection } from '../components/study-goals/RecommendedDecksSection'
import { StudyGoalsFooter } from '../components/study-goals/StudyGoalsFooter'

export function StudyGoalsPage() {
  const { t } = useTranslation('settings')
  const {
    preferences,
    setSubject,
    setLevel,
    setDailyTarget,
    setStudyTime,
    recommendedDecks,
    isDecksLoading,
    installedDeckIds,
    installingDeckId,
    installDeck,
    isSaved,
    currentSubjectConfig,
    currentLevelLabel,
    currentDailyTargetObj,
    currentStudyTimeObj,
    handleSave,
    handleResetDefaults,
  } = useStudyGoals()

  return (
    <Page className="max-w-5xl mx-auto space-y-6 sm:space-y-8 pb-16 px-3 sm:px-6">
      {/* Page Header */}
      <PageHeader
        title={t('study_goals.header.title')}
        description={t('study_goals.header.description')}
        actions={
          <div className="flex items-center gap-2">
            <ContextHelpButton
              guidePath="/guide/dashboard/deck-grouping"
              guideTitle={t('study_goals.header.guide_title')}
              label={t('study_goals.header.help_btn')}
            />
            <Button
              onClick={handleSave}
              className="bg-primary text-primary-foreground font-semibold rounded-lg h-9 px-3.5 shadow-xs"
            >
              {isSaved ? (
                <>
                  <CheckCircle2 className="size-4 mr-1.5" /> {t('study_goals.actions.saved')}
                </>
              ) : (
                <>
                  <Save className="size-4 mr-1.5" /> {t('study_goals.actions.save')}
                </>
              )}
            </Button>
          </div>
        }
      />

      {/* Current Goal Summary Card */}
      <StudyGoalSummaryCard
        preferences={preferences}
        currentSubjectConfig={currentSubjectConfig}
        currentLevelLabel={currentLevelLabel}
        currentDailyTargetObj={currentDailyTargetObj}
        currentStudyTimeObj={currentStudyTimeObj}
      />

      {/* SECTION 1: Subject / Language Selection */}
      <SubjectSelectSection
        selectedSubject={preferences.targetSubject}
        onSelectSubject={setSubject}
      />

      {/* SECTION 2: Target Level Selection */}
      <LevelSelectSection
        currentSubjectConfig={currentSubjectConfig}
        selectedLevel={preferences.frameworkLevel}
        onSelectLevel={setLevel}
      />

      {/* SECTION 3: Daily Target Selection */}
      <DailyTargetSection
        selectedDailyTarget={preferences.dailyNewCards}
        onSelectDailyTarget={setDailyTarget}
      />

      {/* SECTION 4: Preferred Study Time */}
      <StudyTimeSection
        selectedStudyTime={preferences.preferredStudyTime}
        onSelectStudyTime={setStudyTime}
      />

      {/* SECTION 5: Recommended Decks or Empty Deck Guide Fallback */}
      <RecommendedDecksSection
        isDecksLoading={isDecksLoading}
        recommendedDecks={recommendedDecks}
        installedDeckIds={installedDeckIds}
        installingDeckId={installingDeckId}
        onInstallDeck={installDeck}
      />

      {/* Bottom Action Footer */}
      <StudyGoalsFooter
        isSaved={isSaved}
        onResetDefaults={handleResetDefaults}
        onSave={handleSave}
      />
    </Page>
  )
}

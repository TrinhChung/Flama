import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  DAILY_TARGET_OPTIONS,
  STUDY_TIME_OPTIONS,
  SUBJECT_OPTIONS,
} from '@/features/onboarding/constants'
import {
  savePreferences,
  markUserOnboardingCompleted,
  useOnboarding,
} from '@/features/onboarding/hooks/useOnboarding'

export function useStudyGoals() {
  const { t } = useTranslation('settings')
  const onboarding = useOnboarding()
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
  } = onboarding

  const [isSaved, setIsSaved] = useState(false)

  const currentSubjectConfig =
    SUBJECT_OPTIONS.find((s) => s.id === preferences.targetSubject) || SUBJECT_OPTIONS[0]
  const currentLevelObj = currentSubjectConfig.levels.find(
    (l) => l.id === preferences.frameworkLevel,
  )
  const currentLevelLabel = currentLevelObj?.label || preferences.frameworkLevel.toUpperCase()
  const currentDailyTargetObj =
    DAILY_TARGET_OPTIONS.find((d) => d.value === preferences.dailyNewCards) ||
    DAILY_TARGET_OPTIONS[1]
  const currentStudyTimeObj =
    STUDY_TIME_OPTIONS.find((t) => t.value === preferences.preferredStudyTime) ||
    STUDY_TIME_OPTIONS[2]

  const handleSave = () => {
    savePreferences(preferences)
    markUserOnboardingCompleted()
    setIsSaved(true)
    toast.success(t('study_goals.actions.toast_save_success'))
    setTimeout(() => setIsSaved(false), 2500)
  }

  const handleResetDefaults = () => {
    onboarding.resetOnboarding()
    toast.info(t('study_goals.actions.toast_reset_success'))
  }

  return {
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
    currentLevelObj,
    currentLevelLabel,
    currentDailyTargetObj,
    currentStudyTimeObj,
    handleSave,
    handleResetDefaults,
  }
}

import { useState, useEffect, useCallback, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import {
  DEFAULT_ONBOARDING_PREFERENCES,
  ONBOARDING_COMPLETED_KEY,
  ONBOARDING_STORAGE_KEY,
  SUBJECT_OPTIONS,
  CURATED_STARTER_DECKS,
} from '../constants'
import type {
  DailyTargetOption,
  OnboardingPreferences,
  OnboardingSubject,
  RecommendedDeckItem,
  StudyTimeOption,
} from '../types'

export function loadSavedPreferences(): OnboardingPreferences {
  try {
    const raw = localStorage.getItem(ONBOARDING_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return { ...DEFAULT_ONBOARDING_PREFERENCES, ...parsed }
    }
  } catch {
    // Ignore JSON errors
  }
  return DEFAULT_ONBOARDING_PREFERENCES
}

export function savePreferences(prefs: OnboardingPreferences): void {
  try {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(prefs))
  } catch {
    // Ignore localStorage errors
  }
}

export function isUserOnboardingCompleted(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_COMPLETED_KEY) === 'true'
  } catch {
    return false
  }
}

export function markUserOnboardingCompleted(): void {
  try {
    localStorage.setItem(ONBOARDING_COMPLETED_KEY, 'true')
  } catch {
    // Ignore localStorage errors
  }
}

export interface UseOnboardingReturn {
  isOpen: boolean
  step: 1 | 2 | 3 | 4
  preferences: OnboardingPreferences
  isCompleted: boolean
  selectedSubjectConfig: typeof SUBJECT_OPTIONS[0]
  recommendedDecks: RecommendedDeckItem[]
  isDecksLoading: boolean
  installedDeckIds: Set<string>
  installingDeckId: string | null
  openOnboarding: (step?: 1 | 2 | 3 | 4) => void
  closeOnboarding: () => void
  nextStep: () => void
  prevStep: () => void
  setSubject: (subject: OnboardingSubject) => void
  setLevel: (level: string, band?: 'beginner' | 'intermediate' | 'advanced') => void
  setDailyTarget: (target: DailyTargetOption) => void
  setStudyTime: (time: StudyTimeOption) => void
  installDeck: (deck: RecommendedDeckItem) => Promise<void>
  completeOnboarding: () => void
  resetOnboarding: () => void
}

export function useOnboarding(hasUserDecks = false): UseOnboardingReturn {
  const queryClient = useQueryClient()
  const [isOpen, setIsOpen] = useState<boolean>(false)
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1)
  const [preferences, setPreferences] = useState<OnboardingPreferences>(loadSavedPreferences)
  const [installedDeckIds, setInstalledDeckIds] = useState<Set<string>>(
    () => new Set(preferences.installedDeckIds || []),
  )
  const [installingDeckId, setInstallingDeckId] = useState<string | null>(null)
  const [isCompleted, setIsCompleted] = useState<boolean>(isUserOnboardingCompleted)

  // Auto open for first-time visitors with no decks and who haven't completed onboarding
  useEffect(() => {
    if (!isUserOnboardingCompleted() && !hasUserDecks) {
      const timer = setTimeout(() => {
        setIsOpen(true)
      }, 500)
      return () => clearTimeout(timer)
    }
  }, [hasUserDecks])

  const selectedSubjectConfig = useMemo(() => {
    return (
      SUBJECT_OPTIONS.find((s) => s.id === preferences.targetSubject) ||
      SUBJECT_OPTIONS[0]
    )
  }, [preferences.targetSubject])

  // Fetch recommended decks from Marketplace
  const decksQuery = useQuery({
    queryKey: [
      'onboarding-recommended-decks',
      preferences.targetSubject,
      preferences.frameworkLevel,
    ],
    queryFn: async () => {
      try {
        const res = await appApi.get<{ items: RecommendedDeckItem[] }>(
          '/api/shared/decks',
          {
            subject: preferences.targetSubject,
            framework_level: preferences.frameworkLevel,
            pricing_mode: 'free',
            sort: 'top_rated',
          },
        )
        return res.items || []
      } catch {
        return []
      }
    },
    staleTime: 1000 * 60 * 5,
  })

  // Merge API results with curated starter decks for seamless experience
  const recommendedDecks = useMemo(() => {
    const apiDecks = decksQuery.data || []
    const curated = CURATED_STARTER_DECKS[preferences.targetSubject] || []

    if (apiDecks.length > 0) {
      // Return api decks combined with curated items that don't overlap
      const ids = new Set(apiDecks.map((d) => d.id))
      const extraCurated = curated.filter((c) => !ids.has(c.id))
      return [...apiDecks, ...extraCurated].slice(0, 6)
    }

    return curated
  }, [decksQuery.data, preferences.targetSubject])

  // Install mutation
  const installMutation = useMutation({
    mutationFn: async (deck: RecommendedDeckItem) => {
      setInstallingDeckId(deck.id)
      if (deck.id.startsWith('curated-')) {
        // Simulated starter pack clone
        await new Promise((resolve) => setTimeout(resolve, 600))
        return { success: true, simulated: true, title: deck.title }
      }
      return appApi.mutate<{ installed_deck_id?: number }>(
        `/api/shared/decks/${deck.id}/install`,
        'POST',
      )
    },
    onSuccess: (_data, variables) => {
      setInstalledDeckIds((prev) => {
        const next = new Set(prev)
        next.add(variables.id)
        return next
      })

      setPreferences((prev) => {
        const updated = {
          ...prev,
          installedDeckIds: Array.from(new Set([...prev.installedDeckIds, variables.id])),
        }
        savePreferences(updated)
        return updated
      })

      toast.success(`Đã cài đặt "${variables.title}" vào Thư viện của bạn!`, {
        description: 'Bộ thẻ đã sẵn sàng trên Dashboard để bạn bắt đầu học.',
      })

      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['installed-decks'] })
      queryClient.invalidateQueries({ queryKey: ['marketplace'] })
    },
    onError: (err: any) => {
      toast.error('Không thể cài đặt bộ thẻ', {
        description: err?.message || 'Vui lòng thử lại sau hoặc vào Marketplace.',
      })
    },
    onSettled: () => {
      setInstallingDeckId(null)
    },
  })

  const installDeck = useCallback(
    async (deck: RecommendedDeckItem) => {
      if (installedDeckIds.has(deck.id) || installingDeckId === deck.id) return
      await installMutation.mutateAsync(deck)
    },
    [installedDeckIds, installingDeckId, installMutation],
  )

  const openOnboarding = useCallback((targetStep?: 1 | 2 | 3 | 4) => {
    if (targetStep) setStep(targetStep)
    setIsOpen(true)
  }, [])

  const closeOnboarding = useCallback(() => {
    setIsOpen(false)
  }, [])

  const nextStep = useCallback(() => {
    setStep((prev) => (prev < 4 ? ((prev + 1) as 1 | 2 | 3 | 4) : prev))
  }, [])

  const prevStep = useCallback(() => {
    setStep((prev) => (prev > 1 ? ((prev - 1) as 1 | 2 | 3 | 4) : prev))
  }, [])

  const setSubject = useCallback((subject: OnboardingSubject) => {
    const config = SUBJECT_OPTIONS.find((s) => s.id === subject) || SUBJECT_OPTIONS[0]
    setPreferences((prev) => {
      const updated: OnboardingPreferences = {
        ...prev,
        targetSubject: subject,
        frameworkLevel: config.defaultLevel,
        difficultyBand: config.levels[0]?.difficulty_band || 'beginner',
      }
      savePreferences(updated)
      return updated
    })
  }, [])

  const setLevel = useCallback(
    (level: string, band?: 'beginner' | 'intermediate' | 'advanced') => {
      setPreferences((prev) => {
        const currentConfig =
          SUBJECT_OPTIONS.find((s) => s.id === prev.targetSubject) || SUBJECT_OPTIONS[0]
        const matchedLevel = currentConfig.levels.find((l) => l.id === level)
        const updated: OnboardingPreferences = {
          ...prev,
          frameworkLevel: level,
          difficultyBand: band || matchedLevel?.difficulty_band || 'beginner',
        }
        savePreferences(updated)
        return updated
      })
    },
    [],
  )

  const setDailyTarget = useCallback((target: DailyTargetOption) => {
    setPreferences((prev) => {
      const updated: OnboardingPreferences = {
        ...prev,
        dailyNewCards: target,
      }
      savePreferences(updated)
      return updated
    })
  }, [])

  const setStudyTime = useCallback((time: StudyTimeOption) => {
    setPreferences((prev) => {
      const updated: OnboardingPreferences = {
        ...prev,
        preferredStudyTime: time,
      }
      savePreferences(updated)
      return updated
    })
  }, [])

  const completeOnboarding = useCallback(() => {
    const updated: OnboardingPreferences = {
      ...preferences,
      completedAt: new Date().toISOString(),
    }
    setPreferences(updated)
    savePreferences(updated)
    markUserOnboardingCompleted()
    setIsCompleted(true)
    setIsOpen(false)
  }, [preferences])

  const resetOnboarding = useCallback(() => {
    try {
      localStorage.removeItem(ONBOARDING_COMPLETED_KEY)
      localStorage.removeItem(ONBOARDING_STORAGE_KEY)
    } catch {
      // Ignore
    }
    setPreferences(DEFAULT_ONBOARDING_PREFERENCES)
    setInstalledDeckIds(new Set())
    setIsCompleted(false)
    setStep(1)
    setIsOpen(true)
  }, [])

  return {
    isOpen,
    step,
    preferences,
    isCompleted,
    selectedSubjectConfig,
    recommendedDecks,
    isDecksLoading: decksQuery.isPending,
    installedDeckIds,
    installingDeckId,
    openOnboarding,
    closeOnboarding,
    nextStep,
    prevStep,
    setSubject,
    setLevel,
    setDailyTarget,
    setStudyTime,
    installDeck,
    completeOnboarding,
    resetOnboarding,
  }
}

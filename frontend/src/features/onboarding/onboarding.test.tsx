// @vitest-environment jsdom

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/shared/config/i18n'
import {
  DEFAULT_ONBOARDING_PREFERENCES,
  SUBJECT_OPTIONS,
  DAILY_TARGET_OPTIONS,
} from './constants'
import {
  loadSavedPreferences,
  savePreferences,
  isUserOnboardingCompleted,
  markUserOnboardingCompleted,
} from './hooks/useOnboarding'
import { OnboardingHeroCard } from './components/OnboardingHeroCard'
import { OnboardingModal } from './components/OnboardingModal'
import { DashboardSpotlightTour } from './components/DashboardSpotlightTour'

describe('Onboarding Storage & Preferences Helpers', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('loads default preferences when localStorage is empty', () => {
    const prefs = loadSavedPreferences()
    expect(prefs.targetSubject).toBe('japanese')
    expect(prefs.dailyNewCards).toBe(10)
    expect(prefs.frameworkLevel).toBe('n5')
  })

  it('saves and loads preferences correctly from localStorage', () => {
    const custom = {
      ...DEFAULT_ONBOARDING_PREFERENCES,
      targetSubject: 'english' as const,
      frameworkLevel: 'toeic_600',
      dailyNewCards: 20 as const,
    }
    savePreferences(custom)
    const loaded = loadSavedPreferences()
    expect(loaded.targetSubject).toBe('english')
    expect(loaded.frameworkLevel).toBe('toeic_600')
    expect(loaded.dailyNewCards).toBe(20)
  })

  it('checks and marks onboarding completed', () => {
    expect(isUserOnboardingCompleted()).toBe(false)
    markUserOnboardingCompleted()
    expect(isUserOnboardingCompleted()).toBe(true)
  })
})

describe('Onboarding Constants & Configs', () => {
  it('has valid subject options with non-empty levels', () => {
    expect(SUBJECT_OPTIONS.length).toBeGreaterThanOrEqual(5)
    SUBJECT_OPTIONS.forEach((subj) => {
      expect(subj.id).toBeDefined()
      expect(subj.title).toBeDefined()
      expect(subj.levels.length).toBeGreaterThan(0)
    })
  })

  it('has daily target options including 5, 10, 20, 30', () => {
    const values = DAILY_TARGET_OPTIONS.map((d) => d.value)
    expect(values).toContain(5)
    expect(values).toContain(10)
    expect(values).toContain(20)
    expect(values).toContain(30)
  })
})

describe('OnboardingHeroCard Component', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(async () => {
    await i18n.changeLanguage('vi')
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await i18n.changeLanguage('vi')
    act(() => root.unmount())
    container.remove()
  })

  it('renders target information and action buttons in Vietnamese and English', async () => {
    const onOpenPreferences = vi.fn()
    const onOpenCreateDeck = vi.fn()
    const onStartTour = vi.fn()

    await act(async () => {
      root.render(
        <MemoryRouter>
          <OnboardingHeroCard
            preferences={DEFAULT_ONBOARDING_PREFERENCES}
            onOpenPreferences={onOpenPreferences}
            onOpenCreateDeck={onOpenCreateDeck}
            onStartTour={onStartTour}
            hasDecks={true}
          />
        </MemoryRouter>,
      )
    })

    expect(container.textContent).toContain('Mục Tiêu Học Tập')
    expect(container.textContent).toContain('Tiếng Nhật')
    expect(container.textContent).toContain('10 thẻ mới / ngày')
    expect(container.textContent).toContain('Đổi mục tiêu')
    expect(container.textContent).toContain('Tour Hướng Dẫn')

    // Click on "Đổi mục tiêu"
    const changeGoalBtn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Đổi mục tiêu'),
    )
    expect(changeGoalBtn).toBeDefined()
    await act(async () => {
      changeGoalBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(onOpenPreferences).toHaveBeenCalledTimes(1)

    // Switch to English and verify dynamic localization
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(container.textContent).toContain('Learning Goals')
    expect(container.textContent).toContain('Japanese')
    expect(container.textContent).toContain('10 new cards / day')
    expect(container.textContent).toContain('Change Goal')
    expect(container.textContent).toContain('Guide Tour')

    const tourBtnEn = Array.from(container.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Guide Tour'),
    )
    expect(tourBtnEn).toBeDefined()
    await act(async () => {
      tourBtnEn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(onStartTour).toHaveBeenCalledTimes(1)
  })
})

describe('DashboardSpotlightTour Component', () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it('renders when isOpen is true', async () => {
    const onClose = vi.fn()
    await act(async () => {
      root.render(
        <DashboardSpotlightTour
          isOpen={true}
          onClose={onClose}
          hasDecks={true}
        />,
      )
    })

    // Spotlight tour renders mask and elements
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('does not render when isOpen is false', async () => {
    await act(async () => {
      root.render(
        <DashboardSpotlightTour
          isOpen={false}
          onClose={vi.fn()}
          hasDecks={false}
        />,
      )
    })

    expect(container.innerHTML).toBe('')
  })
})

describe('OnboardingModal Component & Step Flow', () => {
  let container: HTMLDivElement
  let root: Root
  let queryClient: QueryClient

  beforeEach(async () => {
    await i18n.changeLanguage('vi')
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await i18n.changeLanguage('vi')
    act(() => root.unmount())
    container.remove()
  })

  it('renders step 1 with subjects and advances to next step in Vietnamese and English', async () => {
    const mockOnboarding: any = {
      isOpen: true,
      step: 1,
      preferences: DEFAULT_ONBOARDING_PREFERENCES,
      selectedSubjectConfig: SUBJECT_OPTIONS[0],
      recommendedDecks: [],
      isDecksLoading: false,
      installedDeckIds: new Set(),
      installingDeckId: null,
      closeOnboarding: vi.fn(),
      nextStep: vi.fn(),
      prevStep: vi.fn(),
      setSubject: vi.fn(),
      setLevel: vi.fn(),
      setDailyTarget: vi.fn(),
      setStudyTime: vi.fn(),
      installDeck: vi.fn(),
      completeOnboarding: vi.fn(),
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <OnboardingModal
              onboarding={mockOnboarding}
              onStartDashboardTour={vi.fn()}
            />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    expect(document.body.textContent).toContain('Chào Mừng Bạn Đến Với Flama!')
    expect(document.body.textContent).toContain('Tiếng Nhật')
    expect(document.body.textContent).toContain('Tiếng Anh')
    expect(document.body.textContent).toContain('Tiếp tục')

    // Switch language to English and verify step 1 localization
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(document.body.textContent).toContain('Welcome to Flama!')
    expect(document.body.textContent).toContain('Japanese')
    expect(document.body.textContent).toContain('English')
    expect(document.body.textContent).toContain('Continue')

    // Click "Continue"
    const nextBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Continue'),
    )
    expect(nextBtn).toBeDefined()
    await act(async () => {
      nextBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(mockOnboarding.nextStep).toHaveBeenCalledTimes(1)
  })

  it('renders step 4 completion screen and starts dashboard tour in Vietnamese and English', async () => {
    const onStartTour = vi.fn()
    const mockOnboarding: any = {
      isOpen: true,
      step: 4,
      preferences: DEFAULT_ONBOARDING_PREFERENCES,
      selectedSubjectConfig: SUBJECT_OPTIONS[0],
      recommendedDecks: [],
      isDecksLoading: false,
      installedDeckIds: new Set(['deck-1']),
      installingDeckId: null,
      closeOnboarding: vi.fn(),
      nextStep: vi.fn(),
      prevStep: vi.fn(),
      setSubject: vi.fn(),
      setLevel: vi.fn(),
      setDailyTarget: vi.fn(),
      setStudyTime: vi.fn(),
      installDeck: vi.fn(),
      completeOnboarding: vi.fn(),
    }

    await act(async () => {
      root.render(
        <QueryClientProvider client={queryClient}>
          <MemoryRouter>
            <OnboardingModal
              onboarding={mockOnboarding}
              onStartDashboardTour={onStartTour}
            />
          </MemoryRouter>
        </QueryClientProvider>,
      )
    })

    expect(document.body.textContent).toContain('Chúc mừng bạn! Lộ trình đã sẵn sàng 🎉')
    expect(document.body.textContent).toContain('Vào Dashboard & Bắt Đầu Tour')

    // Switch language to English and verify step 4 localization
    await act(async () => {
      await i18n.changeLanguage('en')
    })

    expect(document.body.textContent).toContain('Congratulations! Your roadmap is ready 🎉')
    expect(document.body.textContent).toContain('Enter Dashboard & Start Tour')

    const finishBtn = Array.from(document.body.querySelectorAll('button')).find((b) =>
      b.textContent?.includes('Enter Dashboard & Start Tour'),
    )
    expect(finishBtn).toBeDefined()
    await act(async () => {
      finishBtn?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    })
    expect(mockOnboarding.completeOnboarding).toHaveBeenCalledTimes(1)
  })
})


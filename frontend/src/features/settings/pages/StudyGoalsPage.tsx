import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Check,
  CheckCircle2,
  Download,
  Goal,
  Loader2,
  Plus,
  RotateCcw,
  Save,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { ContextHelpButton } from '@/features/guide'
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

export function StudyGoalsPage() {
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
    toast.success('Đã lưu thiết lập mục tiêu học tập thành công!')
    setTimeout(() => setIsSaved(false), 2500)
  }

  const handleResetDefaults = () => {
    onboarding.resetOnboarding()
    toast.info('Đã khôi phục thiết lập mục tiêu mặc định.')
  }

  return (
    <Page className="max-w-5xl mx-auto space-y-6 sm:space-y-8 pb-16 px-3 sm:px-6">
      {/* Page Header */}
      <PageHeader
        title="Mục tiêu học tập"
        description="Tùy chỉnh ngôn ngữ, trình độ mục tiêu và số lượng thẻ mới mỗi ngày."
        actions={
          <div className="flex items-center gap-2">
            <ContextHelpButton
              guidePath="/guide/dashboard/deck-grouping"
              guideTitle="Hướng dẫn quản lý và phân nhóm bộ thẻ"
              label="Trợ giúp"
            />
            <Button
              onClick={handleSave}
              className="bg-primary text-primary-foreground font-semibold rounded-lg h-9 px-3.5 shadow-xs"
            >
              {isSaved ? (
                <>
                  <CheckCircle2 className="size-4 mr-1.5" /> Đã lưu
                </>
              ) : (
                <>
                  <Save className="size-4 mr-1.5" /> Lưu mục tiêu
                </>
              )}
            </Button>
          </div>
        }
      />

      {/* Current Goal Summary Card */}
      <Card className="border border-border/80 bg-card rounded-xl shadow-2xs">
        <CardContent className="p-4 sm:p-5 space-y-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Goal className="size-4 text-primary" />
              <span className="text-sm font-bold text-foreground">Mục tiêu hiện tại</span>
            </div>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <Badge variant="outline" className="font-semibold text-primary border-primary/30">
                {currentSubjectConfig.title} • {currentLevelLabel}
              </Badge>
              <Badge variant="secondary" className="font-medium">
                {preferences.dailyNewCards} thẻ mới / ngày
              </Badge>
              <Badge variant="secondary" className="font-medium">
                {currentStudyTimeObj.label}
              </Badge>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Lộ trình học đang áp dụng: <strong>{currentSubjectConfig.title}</strong>, mục tiêu <strong>{preferences.dailyNewCards} thẻ mới/ngày</strong> ({currentDailyTargetObj.timeEstimate}).
          </p>
        </CardContent>
      </Card>

      {/* SECTION 1: Subject / Language Selection */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
          1. Chọn Ngôn ngữ / Lĩnh vực
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {SUBJECT_OPTIONS.map((subj) => {
            const isSelected = preferences.targetSubject === subj.id
            return (
              <div
                key={subj.id}
                onClick={() => setSubject(subj.id)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-colors text-left flex flex-col justify-between space-y-2 ${
                  isSelected
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                    : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-base font-bold text-foreground">{subj.title}</span>
                  {isSelected && (
                    <span className="size-4 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                      <Check className="size-2.5 stroke-[3]" />
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-muted-foreground line-clamp-2">
                  {subj.subtitle}
                </p>
              </div>
            )
          })}
        </div>
      </div>

      {/* SECTION 2: Target Level Selection */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
            2. Trình độ mục tiêu
          </h3>
          <span className="text-xs text-muted-foreground">{currentSubjectConfig.title}</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
          {currentSubjectConfig.levels.map((lvl) => {
            const isSelected = preferences.frameworkLevel === lvl.id
            return (
              <div
                key={lvl.id}
                onClick={() => setLevel(lvl.id, lvl.difficulty_band)}
                className={`p-3 rounded-xl border cursor-pointer transition-colors flex items-center justify-between gap-2 ${
                  isSelected
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                    : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
                }`}
              >
                <span className="text-xs font-medium text-foreground truncate">{lvl.label}</span>
                {isSelected && <Check className="size-3.5 text-primary shrink-0 stroke-[3]" />}
              </div>
            )
          })}
        </div>
      </div>

      {/* SECTION 3: Daily Target Selection */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
          3. Số lượng thẻ mới mỗi ngày
        </h3>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          {DAILY_TARGET_OPTIONS.map((opt) => {
            const isSelected = preferences.dailyNewCards === opt.value
            return (
              <div
                key={opt.value}
                onClick={() => setDailyTarget(opt.value)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-colors flex flex-col justify-between space-y-1.5 ${
                  isSelected
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                    : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-foreground">{opt.label}</span>
                  {isSelected && <Check className="size-3.5 text-primary stroke-[3]" />}
                </div>
                <div className="text-[11px] text-primary font-medium">{opt.timeEstimate}</div>
                <p className="text-[11px] text-muted-foreground line-clamp-2">{opt.description}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* SECTION 4: Preferred Study Time */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
          4. Khung giờ học tập ưu tiên
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
          {STUDY_TIME_OPTIONS.map((timeOpt) => {
            const isSelected = preferences.preferredStudyTime === timeOpt.value
            return (
              <div
                key={timeOpt.value}
                onClick={() => setStudyTime(timeOpt.value)}
                className={`p-3.5 rounded-xl border cursor-pointer transition-colors flex items-center justify-between ${
                  isSelected
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                    : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
                }`}
              >
                <div className="min-w-0">
                  <div className="text-xs font-bold text-foreground">{timeOpt.label}</div>
                  <div className="text-[11px] text-muted-foreground">{timeOpt.sub}</div>
                </div>
                {isSelected && <Check className="size-3.5 text-primary stroke-[3]" />}
              </div>
            )
          })}
        </div>
      </div>

      {/* SECTION 5: Recommended Decks or Empty Deck Guide Fallback */}
      <div className="space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
            5. Bộ thẻ trong thư viện
          </h3>
          <Button asChild variant="ghost" size="sm" className="text-xs font-medium text-muted-foreground hover:text-foreground">
            <Link to="/marketplace/decks">
              Thư viện Marketplace →
            </Link>
          </Button>
        </div>

        {isDecksLoading ? (
          <div className="flex items-center justify-center p-6 border rounded-xl bg-card">
            <Loader2 className="size-4 animate-spin text-primary mr-2" />
            <span className="text-xs text-muted-foreground">Đang kiểm tra bộ thẻ…</span>
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
                    <span className="text-muted-foreground">{deck.card_count} thẻ</span>
                    {isInstalled ? (
                      <Badge variant="secondary" className="text-[10px]">Đã cài</Badge>
                    ) : (
                      <Button
                        size="xs"
                        onClick={() => installDeck(deck)}
                        disabled={isInstalling}
                        className="text-[11px] font-semibold h-7"
                      >
                        {isInstalling ? (
                          <Loader2 className="size-3 animate-spin" />
                        ) : (
                          <>
                            <Download className="size-3 mr-1" /> Cài đặt
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
                Chưa có bộ thẻ phù hợp cho trình độ này trong Thư viện
              </h4>
              <p className="text-xs text-muted-foreground max-w-xl">
                Bạn có thể tự tạo bộ thẻ học flashcard theo nhu cầu cá nhân hoặc tham khảo hướng dẫn chi tiết cách tạo và gom nhóm deck.
              </p>
            </div>

            <div className="flex items-center gap-2 shrink-0 flex-wrap">
              <Button asChild variant="outline" size="sm" className="h-8 text-xs font-semibold rounded-lg">
                <Link to="/guide/dashboard/deck-grouping">
                  <BookOpen className="size-3.5 mr-1.5" />
                  Hướng dẫn tạo thẻ
                </Link>
              </Button>
              <Button asChild size="sm" className="h-8 text-xs font-semibold rounded-lg bg-primary text-primary-foreground">
                <Link to="/dashboard">
                  <Plus className="size-3.5 mr-1.5" />
                  Tạo Deck trên Dashboard
                </Link>
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Action Footer */}
      <div className="p-4 rounded-xl border border-border/80 bg-card flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleResetDefaults}
          className="text-xs text-muted-foreground hover:text-foreground h-8"
        >
          <RotateCcw className="size-3.5 mr-1.5" /> Khôi phục mặc định
        </Button>

        <Button
          type="button"
          size="sm"
          onClick={handleSave}
          className="bg-primary text-primary-foreground font-semibold rounded-lg text-xs h-8 px-4 shadow-xs"
        >
          {isSaved ? (
            <>
              <CheckCircle2 className="size-3.5 mr-1.5" /> Đã lưu
            </>
          ) : (
            <>
              <Save className="size-3.5 mr-1.5" /> Lưu mục tiêu
            </>
          )}
        </Button>
      </div>
    </Page>
  )
}


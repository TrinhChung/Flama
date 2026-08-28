import { useEffect } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Clock,
  Download,
  Flame,
  GraduationCap,
  Layers,
  Loader2,
  Play,
  Star,
  Target,
  X,
  Zap,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DAILY_TARGET_OPTIONS,
  STUDY_TIME_OPTIONS,
  SUBJECT_OPTIONS,
} from '../constants'
import type { UseOnboardingReturn } from '../hooks/useOnboarding'

interface OnboardingModalProps {
  onboarding: UseOnboardingReturn
  onStartDashboardTour?: () => void
}

export function OnboardingModal({
  onboarding,
  onStartDashboardTour,
}: OnboardingModalProps) {
  const {
    isOpen,
    step,
    preferences,
    selectedSubjectConfig,
    recommendedDecks,
    isDecksLoading,
    installedDeckIds,
    installingDeckId,
    closeOnboarding,
    nextStep,
    prevStep,
    setSubject,
    setLevel,
    setDailyTarget,
    setStudyTime,
    installDeck,
    completeOnboarding,
  } = onboarding

  const handleFinishAndStartTour = () => {
    completeOnboarding()
    if (onStartDashboardTour) {
      setTimeout(() => {
        onStartDashboardTour()
      }, 300)
    }
  }

  // Keyboard navigation for power users
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeOnboarding()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, closeOnboarding])

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && closeOnboarding()}>
      <DialogContent className="max-w-2xl sm:max-w-3xl p-0 overflow-hidden border-border/80 bg-card rounded-2xl shadow-2xl transition-all">
        {/* Top Header Banner */}
        <div className="relative bg-gradient-to-r from-primary/15 via-orange-500/10 to-amber-500/10 border-b border-border/60 p-5 sm:p-6 pb-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <div className="size-9 rounded-xl bg-gradient-to-br from-primary to-orange-500 text-primary-foreground flex items-center justify-center font-black shadow-md shadow-primary/20">
                <Flame className="size-5" />
              </div>
              <div>
                <DialogTitle className="text-lg sm:text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
                  <span>Chào Mừng Bạn Đến Với Flama!</span>
                  <Badge variant="outline" className="text-[10px] font-bold border-primary/40 text-primary">
                    BƯỚC {step}/4
                  </Badge>
                </DialogTitle>
                <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                  Thiết lập mục tiêu và cá nhân hóa lộ trình học thông minh dành riêng cho bạn
                </DialogDescription>
              </div>
            </div>

            <button
              type="button"
              onClick={closeOnboarding}
              className="size-8 rounded-lg text-muted-foreground hover:text-foreground flex items-center justify-center hover:bg-muted/80 transition-colors"
              title="Đóng"
            >
              <X className="size-4" />
            </button>
          </div>

          {/* Progress Indicator Steps */}
          <div className="grid grid-cols-4 gap-2 pt-5">
            {[
              { num: 1, label: 'Mục Tiêu' },
              { num: 2, label: 'Thói Quen' },
              { num: 3, label: 'Nhận Thẻ' },
              { num: 4, label: 'Hoàn Tất' },
            ].map((s) => {
              const isPast = s.num < step
              const isCurrent = s.num === step
              return (
                <div key={s.num} className="space-y-1.5">
                  <div
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      isCurrent
                        ? 'bg-primary shadow-xs'
                        : isPast
                        ? 'bg-primary/60'
                        : 'bg-muted'
                    }`}
                  />
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-[10px] font-bold ${
                        isCurrent
                          ? 'text-primary'
                          : isPast
                          ? 'text-foreground'
                          : 'text-muted-foreground/60'
                      }`}
                    >
                      {s.num}. {s.label}
                    </span>
                    {isPast && <Check className="size-2.5 text-primary" />}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Modal Body Content by Step */}
        <div className="p-5 sm:p-6 max-h-[62vh] overflow-y-auto space-y-5">
          {/* STEP 1: Select Learning Domain / Subject & Level */}
          {step === 1 && (
            <div className="space-y-5 animate-in fade-in-50 duration-200">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                  <Target className="size-4 text-primary" /> Bạn muốn tập trung học ngôn ngữ hoặc kỹ năng nào?
                </h3>
                <p className="text-xs text-muted-foreground">
                  Chọn chủ đề chính để Flama đề xuất các bộ flashcard và lộ trình học tập phù hợp nhất.
                </p>
              </div>

              {/* Subject Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 sm:gap-3">
                {SUBJECT_OPTIONS.map((subj) => {
                  const isSelected = preferences.targetSubject === subj.id
                  return (
                    <div
                      key={subj.id}
                      onClick={() => setSubject(subj.id)}
                      className={`group relative flex flex-col justify-between p-3.5 rounded-xl border cursor-pointer transition-all duration-200 text-left ${
                        isSelected
                          ? 'border-primary bg-primary/5 ring-2 ring-primary/25 shadow-xs'
                          : `border-border/70 bg-card hover:bg-muted/40 ${subj.borderHover}`
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="text-2xl">{subj.flag}</span>
                          {isSelected && (
                            <span className="size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                              <Check className="size-3 stroke-[3]" />
                            </span>
                          )}
                        </div>
                        <h4 className="text-sm font-bold text-foreground group-hover:text-primary transition-colors">
                          {subj.title}
                        </h4>
                        <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                          {subj.subtitle}
                        </p>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Level Selector for Active Subject */}
              <div className="space-y-2.5 pt-2 border-t border-border/60">
                <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <GraduationCap className="size-3.5 text-primary" />
                  Trình độ hoặc mục tiêu của bạn trong {selectedSubjectConfig.title}:
                </h4>
                <div className="flex flex-wrap gap-2">
                  {selectedSubjectConfig.levels.map((lvl) => {
                    const isSelected = preferences.frameworkLevel === lvl.id
                    return (
                      <button
                        key={lvl.id}
                        type="button"
                        onClick={() => setLevel(lvl.id, lvl.difficulty_band)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                          isSelected
                            ? 'border-primary bg-primary text-primary-foreground shadow-xs'
                            : 'border-border/80 bg-muted/40 text-foreground hover:bg-muted hover:border-primary/40'
                        }`}
                      >
                        {lvl.label}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Study Habits & Daily Card Target */}
          {step === 2 && (
            <div className="space-y-5 animate-in fade-in-50 duration-200">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                  <Zap className="size-4 text-primary" /> Bạn muốn học bao nhiêu thẻ mới mỗi ngày?
                </h3>
                <p className="text-xs text-muted-foreground">
                  Thuật toán Spaced Repetition sẽ phân bổ thẻ mới và thẻ ôn tập (Due) theo nhịp học bền vững của bạn.
                </p>
              </div>

              {/* Daily Target Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {DAILY_TARGET_OPTIONS.map((opt) => {
                  const isSelected = preferences.dailyNewCards === opt.value
                  return (
                    <div
                      key={opt.value}
                      onClick={() => setDailyTarget(opt.value)}
                      className={`relative flex flex-col justify-between p-4 rounded-xl border cursor-pointer transition-all ${
                        isSelected
                          ? `${opt.color} shadow-xs`
                          : 'border-border/70 bg-card hover:bg-muted/40 hover:border-border'
                      }`}
                    >
                      <div className="space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{opt.icon}</span>
                            <span className="text-sm font-bold text-foreground">
                              {opt.label}
                            </span>
                          </div>
                          {opt.badge && (
                            <Badge className="text-[10px] font-bold bg-primary text-primary-foreground">
                              {opt.badge}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs font-semibold text-primary/90 flex items-center gap-1">
                          <Clock className="size-3" /> {opt.timeEstimate}
                        </p>
                        <p className="text-[11px] text-muted-foreground leading-relaxed">
                          {opt.description}
                        </p>
                      </div>

                      <div className="pt-2 flex justify-end">
                        <div
                          className={`size-4 rounded-full border flex items-center justify-center ${
                            isSelected
                              ? 'border-primary bg-primary text-primary-foreground'
                              : 'border-muted-foreground/40'
                          }`}
                        >
                          {isSelected && <Check className="size-2.5 stroke-[3]" />}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Preferred Study Time */}
              <div className="space-y-2.5 pt-3 border-t border-border/60">
                <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Clock className="size-3.5 text-primary" /> Khung giờ bạn thường dành để học:
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {STUDY_TIME_OPTIONS.map((timeOpt) => {
                    const isSelected = preferences.preferredStudyTime === timeOpt.value
                    return (
                      <button
                        key={timeOpt.value}
                        type="button"
                        onClick={() => setStudyTime(timeOpt.value)}
                        className={`flex items-center gap-2.5 p-2.5 rounded-xl border text-left transition-all ${
                          isSelected
                            ? 'border-primary bg-primary/10 text-foreground font-semibold shadow-xs'
                            : 'border-border/70 bg-card hover:bg-muted/50 text-muted-foreground'
                        }`}
                      >
                        <span className="text-lg">{timeOpt.icon}</span>
                        <div>
                          <div className="text-xs font-bold text-foreground">{timeOpt.label}</div>
                          <div className="text-[10px] text-muted-foreground">{timeOpt.sub}</div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Personalized Deck Discovery & 1-Click Install */}
          {step === 3 && (
            <div className="space-y-5 animate-in fade-in-50 duration-200">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                    <Download className="size-4 text-primary" /> Bộ thẻ khởi đầu đề xuất cho bạn
                  </h3>
                  <Badge variant="outline" className="text-[11px] font-semibold border-primary/30 text-primary">
                    {selectedSubjectConfig.title}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Dựa trên mục tiêu đã chọn, đây là các bộ flashcard cộng đồng được tối ưu cho người mới bắt đầu.
                </p>
              </div>

              {/* Recommended Decks List */}
              {isDecksLoading ? (
                <div className="flex flex-col items-center justify-center p-8 space-y-2 text-center">
                  <Loader2 className="size-7 animate-spin text-primary" />
                  <p className="text-xs text-muted-foreground font-medium">
                    Đang tìm kiếm các bộ thẻ chất lượng cao từ Thư viện...
                  </p>
                </div>
              ) : recommendedDecks.length === 0 ? (
                <div className="text-center p-6 border rounded-xl border-dashed border-border/80 bg-muted/20 space-y-2">
                  <p className="text-xs text-muted-foreground">
                    Chưa có bộ thẻ mẫu trực tiếp cho cấp độ này. Bạn có thể tự tạo bộ thẻ đầu tiên trên Dashboard!
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {recommendedDecks.map((deck) => {
                    const isInstalled =
                      installedDeckIds.has(deck.id) ||
                      Boolean(deck.is_installed || deck.installed_deck_id)
                    const isInstalling = installingDeckId === deck.id

                    return (
                      <Card
                        key={deck.id}
                        className={`overflow-hidden border transition-all duration-200 flex flex-col justify-between ${
                          isInstalled
                            ? 'border-emerald-500/50 bg-emerald-500/5 shadow-xs'
                            : 'border-border/80 bg-card hover:border-primary/40'
                        }`}
                      >
                        <CardContent className="p-3.5 space-y-2.5 flex-1 flex flex-col justify-between">
                          <div className="space-y-1.5">
                            <div className="flex items-center justify-between gap-1">
                              <Badge
                                variant="secondary"
                                className="text-[10px] px-1.5 py-0 font-bold bg-muted text-muted-foreground"
                              >
                                {deck.primary_category || selectedSubjectConfig.title}
                              </Badge>
                              {deck.rating_avg ? (
                                <span className="text-[10px] font-bold text-amber-500 flex items-center gap-0.5">
                                  <Star className="size-3 fill-amber-500" /> {Number(deck.rating_avg).toFixed(1)}
                                </span>
                              ) : null}
                            </div>

                            <h4 className="text-xs font-bold text-foreground leading-snug line-clamp-2">
                              {deck.title}
                            </h4>

                            {deck.description && (
                              <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                                {deck.description}
                              </p>
                            )}
                          </div>

                          <div className="pt-2 border-t border-border/50 space-y-2">
                            <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                              <span className="flex items-center gap-1 font-medium">
                                <Layers className="size-3 text-primary" /> {deck.card_count || deck.note_count || 100} thẻ
                              </span>
                              {deck.author?.username && (
                                <span className="truncate max-w-[100px]">
                                  Tác giả: {deck.author.username}
                                </span>
                              )}
                            </div>

                            {isInstalled ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled
                                className="w-full h-8 text-xs font-bold text-emerald-600 dark:text-emerald-400 border-emerald-500/40 bg-emerald-500/10"
                              >
                                <CheckCircle2 className="size-3.5 mr-1.5 text-emerald-500" />
                                Đã cài đặt
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                onClick={() => installDeck(deck)}
                                disabled={isInstalling}
                                className="w-full h-8 text-xs font-bold bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs"
                              >
                                {isInstalling ? (
                                  <>
                                    <Loader2 className="size-3.5 mr-1.5 animate-spin" />
                                    Đang cài đặt…
                                  </>
                                ) : (
                                  <>
                                    <Download className="size-3.5 mr-1.5" />
                                    Thêm vào bộ thẻ
                                  </>
                                )}
                              </Button>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )
                  })}
                </div>
              )}

              {/* Spaced Repetition Educational Note */}
              <div className="p-3 rounded-xl bg-orange-500/10 border border-orange-500/20 text-xs space-y-1">
                <div className="font-bold text-orange-700 dark:text-orange-300 flex items-center gap-1.5">
                  <BookOpen className="size-3.5 text-orange-600 dark:text-orange-400" />
                  Ghi nhớ ngắt quãng (Spaced Repetition System):
                </div>
                <p className="text-[11px] text-muted-foreground leading-relaxed">
                  Bạn không cần học hết tất cả thẻ trong một lần. Hãy học đúng số thẻ mục tiêu mỗi ngày, thuật toán của Flama sẽ tự động xếp lịch ôn tập trước khi bạn quên!
                </p>
              </div>
            </div>
          )}

          {/* STEP 4: Completion & Tour Launch Ready */}
          {step === 4 && (
            <div className="space-y-6 text-center py-4 animate-in fade-in-50 zoom-in-95 duration-200">
              <div className="size-16 mx-auto rounded-2xl bg-gradient-to-tr from-primary to-orange-500 text-primary-foreground flex items-center justify-center shadow-lg shadow-primary/25">
                <CheckCircle2 className="size-8 stroke-[2.5]" />
              </div>

              <div className="space-y-1.5 max-w-md mx-auto">
                <h3 className="text-xl font-bold text-foreground">
                  Chúc mừng bạn! Lộ trình đã sẵn sàng 🎉
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Tài khoản của bạn đã được cá nhân hóa hoàn tất. Giờ hãy cùng khám phá các tính năng chính trên Dashboard nhé!
                </p>
              </div>

              {/* Summary Profile Box */}
              <div className="max-w-md mx-auto p-4 rounded-xl border border-border/80 bg-muted/30 text-left space-y-2.5">
                <div className="text-xs font-bold text-foreground border-b border-border/60 pb-1.5 flex items-center justify-between">
                  <span>Mục Tiêu Cá Nhân Của Bạn:</span>
                  <Badge variant="default" className="text-[10px] font-bold">
                    Hoạt Động
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground text-[11px]">Chủ đề:</span>
                    <p className="font-bold text-foreground">
                      {selectedSubjectConfig.flag} {selectedSubjectConfig.title}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[11px]">Mục tiêu ngày:</span>
                    <p className="font-bold text-foreground">
                      ⚡ {preferences.dailyNewCards} thẻ mới / ngày
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[11px]">Khung giờ học:</span>
                    <p className="font-bold text-foreground capitalize">
                      {preferences.preferredStudyTime === 'morning'
                        ? '🌅 Buổi sáng'
                        : preferences.preferredStudyTime === 'afternoon'
                        ? '☀️ Buổi trưa'
                        : '🌙 Buổi tối'}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground text-[11px]">Bộ thẻ đã cài:</span>
                    <p className="font-bold text-foreground">
                      {installedDeckIds.size > 0
                        ? `📚 ${installedDeckIds.size} bộ thẻ khởi đầu`
                        : 'Sẵn sàng tạo mới'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="p-4 sm:p-5 border-t border-border/60 bg-muted/20 flex items-center justify-between gap-3">
          <div>
            {step > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={prevStep}
                className="h-9 px-3 text-xs font-semibold rounded-xl"
              >
                <ArrowLeft className="size-3.5 mr-1.5" />
                Quay lại
              </Button>
            )}
            {step === 1 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={closeOnboarding}
                className="h-9 px-3 text-xs font-medium text-muted-foreground hover:text-foreground rounded-xl"
              >
                Để sau
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {step < 4 ? (
              <Button
                size="sm"
                onClick={nextStep}
                className="h-9 px-4 text-xs font-bold rounded-xl bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs"
              >
                Tiếp tục
                <ArrowRight className="size-3.5 ml-1.5" />
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleFinishAndStartTour}
                className="h-9 px-5 text-xs font-bold rounded-xl bg-gradient-to-r from-primary to-orange-500 text-primary-foreground hover:opacity-95 shadow-md shadow-primary/20"
              >
                <Play className="size-3.5 mr-1.5 fill-current" />
                Vào Dashboard & Bắt Đầu Tour
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

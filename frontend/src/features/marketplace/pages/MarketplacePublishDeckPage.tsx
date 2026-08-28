import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Sparkles,
} from 'lucide-react'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { loadDeckOptionsForPublish } from '../publishApi'
import { useTaxonomySchema } from '../hooks/useTaxonomySchema'
import {
  CATEGORY_PRESETS,
  TAXONOMY_DIFFICULTIES,
} from '../utils/publishTaxonomyConstants'
import { WIZARD_STEPS } from '../components/publish/PublishWizardTypes'
import { PublishStep1BasicInfo } from '../components/publish/PublishStep1BasicInfo'
import { PublishStep2Taxonomy } from '../components/publish/PublishStep2Taxonomy'
import { PublishStep3Goals } from '../components/publish/PublishStep3Goals'
import { PublishStep4Pricing } from '../components/publish/PublishStep4Pricing'

export function MarketplacePublishDeckPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryParamDeckId = searchParams.get('deck_id') || searchParams.get('id') || searchParams.get('source_deck_id') || ''
  const deckItemId = searchParams.get('deck_item_id') || ''
  const isEditMode = searchParams.get('edit') === '1' && Boolean(deckItemId)

  const [sourceDeckId, setSourceDeckId] = useState<string>(queryParamDeckId)
  const [title, setTitle] = useState('')
  const [isTitleManuallyEdited, setIsTitleManuallyEdited] = useState(false)
  const [previewText, setPreviewText] = useState('')
  const [description, setDescription] = useState('')
  const [distributionMode, setDistributionMode] = useState<'free' | 'paid' | 'course_key'>('free')
  const [pricingMode, setPricingMode] = useState<'free' | 'paid'>('free')
  const [priceAmountMinor, setPriceAmountMinor] = useState<number>(10000)
  const [studentOfferMode, setStudentOfferMode] = useState<'none' | 'free' | 'percent_discount'>('none')
  const [studentDiscountPercent, setStudentDiscountPercent] = useState<number | null>(null)
  const [courseTitle, setCourseTitle] = useState('')
  const [courseDescription, setCourseDescription] = useState('')
  const [courseUrl, setCourseUrl] = useState('')
  const [courseInstructions, setCourseInstructions] = useState('')
  const [version, setVersion] = useState('1.0.0')
  const [tags, setTags] = useState('')
  const [changelog, setChangelog] = useState('')
  const [primaryCategory, setPrimaryCategory] = useState('General')
  const [customCategory, setCustomCategory] = useState('')
  const [subcategory, setSubcategory] = useState('')
  const [targetAudience, setTargetAudience] = useState('')

  // Taxonomy states
  const [taxonomyDomain, setTaxonomyDomain] = useState('language_learning')
  const [taxonomySubject, setTaxonomySubject] = useState('japanese')
  const [taxonomyFramework, setTaxonomyFramework] = useState('')
  const [taxonomyFrameworkLevel, setTaxonomyFrameworkLevel] = useState('')
  const [taxonomyDifficulty, setTaxonomyDifficulty] = useState('beginner')
  const [taxonomyGoals, setTaxonomyGoals] = useState<string[]>(['vocabulary'])
  const [taxonomyTopics, setTaxonomyTopics] = useState<string[]>(['meaning_recall'])
  
  // Wizard Step state
  const [currentStep, setCurrentStep] = useState<number>(1)

  // Field validation errors
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const clearFieldError = (name: string) => {
    if (fieldErrors[name]) {
      setFieldErrors((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
    }
  }

  const decksQuery = useQuery({
    queryKey: ['my-decks-for-publish'],
    queryFn: loadDeckOptionsForPublish,
  })

  // Load existing details for edit mode
  const deckItemQuery = useQuery({
    queryKey: ['shared-deck-detail-edit', deckItemId],
    queryFn: () => appApi.get<any>(`/api/shared/decks/${deckItemId}`),
    enabled: isEditMode && Boolean(deckItemId),
  })

  const deckItem = deckItemQuery.data
  const isReleaseVersioned = Boolean(
    isEditMode && (deckItem?.release_versioned || deckItem?.current_release_id),
  )

  // Populate form states from edit data
  useEffect(() => {
    if (isEditMode && deckItem) {
      if (deckItem.source_deck_id) setSourceDeckId(String(deckItem.source_deck_id))
      setTitle(deckItem.title || '')
      setPreviewText(deckItem.preview_text || '')
      setDescription(deckItem.description || '')
      if (deckItem.distribution_mode) {
        setDistributionMode(deckItem.distribution_mode)
      } else if (deckItem.pricing_mode === 'paid') {
        setDistributionMode('paid')
      } else {
        setDistributionMode('free')
      }
      setCourseTitle(deckItem.course_title || '')
      setCourseDescription(deckItem.course_description || '')
      setCourseUrl(deckItem.course_url || '')
      setCourseInstructions(deckItem.course_instructions || '')
      setPricingMode(deckItem.pricing_mode || 'free')
      setPriceAmountMinor(deckItem.price_amount_minor || 10000)
      setStudentOfferMode(deckItem.student_offer_mode || 'none')
      setStudentDiscountPercent(deckItem.student_discount_percent || null)
      setVersion(deckItem.version || '1.0.0')
      setTags(deckItem.tags ? deckItem.tags.join(', ') : '')
      setChangelog(deckItem.changelog || '')
      
      const cat = deckItem.primary_category || 'General'
      const categoryPresetsValues = CATEGORY_PRESETS.map(p => p.id)
      if (categoryPresetsValues.includes(cat)) {
        setPrimaryCategory(cat)
        setCustomCategory('')
      } else {
        setPrimaryCategory('Custom')
        setCustomCategory(cat)
      }

      setSubcategory(deckItem.taxonomy_metadata?.subcategory || '')
      setTargetAudience(deckItem.taxonomy_metadata?.target_audience || '')
      setTaxonomyDomain(deckItem.taxonomy_metadata?.domain || 'language_learning')
      setTaxonomySubject(deckItem.taxonomy_metadata?.subject || 'japanese')
      setTaxonomyFramework(deckItem.taxonomy_metadata?.framework || '')
      setTaxonomyFrameworkLevel(deckItem.taxonomy_metadata?.framework_level || '')
      setTaxonomyDifficulty(deckItem.taxonomy_metadata?.difficulty_band || 'beginner')
      setTaxonomyGoals(deckItem.taxonomy_metadata?.learning_goals || ['vocabulary'])
      setTaxonomyTopics(deckItem.taxonomy_metadata?.primary_topics || ['meaning_recall'])
    }
  }, [isEditMode, deckItem])

  const effectiveCategory = primaryCategory === 'Custom' ? customCategory.trim() || 'Khác' : primaryCategory

  const publishMutation = useMutation({
    mutationFn: () => {
      const endpoint = isEditMode ? `/api/shared/decks/${deckItemId}` : '/api/shared/decks'
      const method = isEditMode ? 'PATCH' : 'POST'
      const effectiveSourceDeckId = isEditMode
        ? Number(deckItem?.source_deck_id || sourceDeckId)
        : Number(sourceDeckId)

      const releaseMetadata = isReleaseVersioned
        ? {}
        : {
            version: version.trim() || '1.0.0',
            changelog: changelog.trim(),
          }

      return appApi.mutate(endpoint, method, {
        source_deck_id: effectiveSourceDeckId,
        title: title.trim(),
        preview_text: previewText.trim(),
        description: description.trim(),
        distribution_mode: distributionMode,
        pricing_mode: distributionMode === 'course_key' ? 'free' : pricingMode,
        price_amount_minor: distributionMode === 'paid' ? priceAmountMinor : 0,
        student_offer_mode: distributionMode === 'paid' ? studentOfferMode : 'none',
        student_discount_percent:
          distributionMode === 'paid' && studentOfferMode === 'percent_discount'
            ? studentDiscountPercent
            : null,
        course_title: distributionMode === 'course_key' ? courseTitle.trim() || undefined : undefined,
        course_description: distributionMode === 'course_key' ? courseDescription.trim() || undefined : undefined,
        course_url: distributionMode === 'course_key' ? courseUrl.trim() || undefined : undefined,
        course_instructions: distributionMode === 'course_key' ? courseInstructions.trim() || undefined : undefined,
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        primary_category: effectiveCategory,
        taxonomy_domain: taxonomyDomain,
        taxonomy_subject: taxonomySubject,
        taxonomy_framework: taxonomyFramework || undefined,
        taxonomy_framework_level: taxonomyFrameworkLevel || undefined,
        difficulty_band: taxonomyDifficulty,
        subcategory: subcategory.trim() || undefined,
        target_audience: targetAudience.trim() || undefined,
        learning_goals: taxonomyGoals,
        primary_topics: taxonomyTopics,
        ...releaseMetadata,
      })
    },
    onSuccess: (data: any) => {
      const publishedId = data?.deck_marketplace_item?.id || data?.shared_deck?.id || deckItemId
      toast.success(
        isEditMode
          ? 'Đã cập nhật thông tin bộ thẻ trên Marketplace!'
          : 'Xuất bản bộ thẻ thành công! Bạn có thể quản lý release và phiên bản tại đây.',
      )
      if (publishedId) {
        navigate(`/marketplace/decks/${publishedId}`)
      } else {
        navigate('/marketplace/decks')
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Không thể đăng tải bộ thẻ. Vui lòng kiểm tra lại thông tin.')
    },
  })

  const taxonomySchema = useTaxonomySchema('deck_marketplace_item')
  const availableDomains = taxonomySchema.domains
  const availableSubjects = taxonomySchema.subjectsByDomain(taxonomyDomain)
  const availableFrameworks = useMemo(
    () => taxonomySchema.frameworksForSubject(taxonomySubject),
    [taxonomySchema, taxonomySubject],
  )
  const activeFramework = useMemo(
    () => availableFrameworks.find((f) => f.id === taxonomyFramework) || availableFrameworks[0] || null,
    [availableFrameworks, taxonomyFramework],
  )
  const availableGoals = useMemo(
    () => taxonomySchema.goalsForSubject(taxonomySubject, taxonomyDomain),
    [taxonomySchema, taxonomySubject, taxonomyDomain],
  )
  const availableTopics = useMemo(
    () => taxonomySchema.topicsForSubject(taxonomySubject, taxonomyDomain),
    [taxonomySchema, taxonomySubject, taxonomyDomain],
  )

  const decks = useMemo(() => decksQuery.data?.items || [], [decksQuery.data])

  useEffect(() => {
    if (!sourceDeckId && decks.length > 0 && !isEditMode) {
      setSourceDeckId(String(decks[0].id))
      if (!isTitleManuallyEdited) {
        setTitle(decks[0].name)
      }
    }
  }, [decks, sourceDeckId, isTitleManuallyEdited, isEditMode])

  const selectedDeck = useMemo(
    () => decks.find((d) => String(d.id) === String(sourceDeckId)),
    [decks, sourceDeckId],
  )

  // Wizard Step Validation
  const validateStep = (stepNumber: number): boolean => {
    const errors: Record<string, string> = {}

    if (stepNumber === 1) {
      if (!sourceDeckId && !isEditMode) {
        errors.sourceDeckId = 'Vui lòng chọn một bộ thẻ nguồn để chia sẻ'
      }
      if (!title.trim()) {
        errors.title = 'Vui lòng nhập tiêu đề hiển thị cho bộ thẻ'
      } else if (title.trim().length < 3) {
        errors.title = 'Tiêu đề quá ngắn (tối thiểu 3 ký tự)'
      }
      if (!previewText.trim()) {
        errors.previewText = 'Vui lòng nhập tóm tắt xem trước ngắn (Preview text)'
      } else if (previewText.trim().length < 10) {
        errors.previewText = 'Tóm tắt quá ngắn (tối thiểu 10 ký tự)'
      }
      if (!description.trim()) {
        errors.description = 'Vui lòng nhập mô tả chi tiết cho bộ thẻ'
      }
    }

    if (stepNumber === 2) {
      if (!taxonomyDomain) {
        errors.taxonomyDomain = 'Vui lòng chọn lĩnh vực học tập'
      }
      if (!taxonomySubject) {
        errors.taxonomySubject = 'Vui lòng chọn môn học / ngôn ngữ'
      }
      if (!taxonomyDifficulty) {
        errors.taxonomyDifficulty = 'Vui lòng chọn mức độ khó'
      }
      if (primaryCategory === 'Custom' && !customCategory.trim()) {
        errors.customCategory = 'Vui lòng nhập tên danh mục tùy chỉnh'
      }
    }

    if (stepNumber === 3) {
      if (taxonomyGoals.length === 0) {
        errors.taxonomyGoals = 'Vui lòng chọn ít nhất 1 mục tiêu học tập'
      }
      if (taxonomyTopics.length === 0) {
        errors.taxonomyTopics = 'Vui lòng chọn ít nhất 1 chủ đề trọng tâm'
      }
    }

    if (stepNumber === 4) {
      if (distributionMode === 'paid') {
        if (!priceAmountMinor || priceAmountMinor < 1000) {
          errors.price = 'Giá bán phải tối thiểu từ 1.000 VNĐ'
        }
        if (
          studentOfferMode === 'percent_discount' &&
          (!studentDiscountPercent || studentDiscountPercent < 1 || studentDiscountPercent > 99)
        ) {
          errors.student_discount_percent = 'Vui lòng nhập phần trăm giảm giá hợp lệ (1-99%)'
        }
      }
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handlePublish = () => {
    for (let step = 1; step <= 4; step++) {
      if (!validateStep(step)) {
        setCurrentStep(step)
        toast.error(`Vui lòng hoàn thành các thông tin bắt buộc tại Bước ${step}`)
        return
      }
    }
    publishMutation.mutate()
  }

  const handleNextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 4))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      toast.error('Vui lòng kiểm tra và điền đủ thông tin trước khi chuyển bước')
    }
  }

  const handlePrevStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const goToStep = (targetStep: number) => {
    if (targetStep < currentStep) {
      setCurrentStep(targetStep)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else if (targetStep > currentStep) {
      let canProceed = true
      for (let s = currentStep; s < targetStep; s++) {
        if (!validateStep(s)) {
          canProceed = false
          setCurrentStep(s)
          toast.error(`Vui lòng hoàn thiện Bước ${s} trước`)
          break
        }
      }
      if (canProceed) {
        setCurrentStep(targetStep)
        window.scrollTo({ top: 0, behavior: 'smooth' })
      }
    }
  }

  if (decksQuery.isPending || (isEditMode && deckItemQuery.isPending)) {
    return <PageLoading label="Đang tải dữ liệu..." />
  }

  if (decksQuery.error) {
    return (
      <Page>
        <PageError error={decksQuery.error} />
      </Page>
    )
  }

  if (isEditMode && deckItemQuery.error) {
    return (
      <Page>
        <PageError error={deckItemQuery.error} />
      </Page>
    )
  }

  return (
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6 max-w-7xl mx-auto">
      <AmbientBackground intensity="subtle" />

      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-border/80 bg-card/60 p-4 sm:p-6 shadow-xs backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="border-border/80 bg-muted font-bold text-[11px] px-2.5 py-0.5 text-foreground">
                Flama Creator Hub
              </Badge>
              <Badge variant="outline" className="text-[11px] font-medium text-muted-foreground">
                Đa môn học & Lĩnh vực
              </Badge>
            </div>
            <h1 className="text-xl sm:text-2xl md:text-3xl font-black tracking-tight text-foreground">
              {isEditMode ? 'Chỉnh sửa thông tin chia sẻ Bộ thẻ' : 'Chia sẻ Bộ thẻ vào Marketplace'}
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed max-w-3xl">
              {isEditMode 
                ? 'Cập nhật lại các thông tin mô tả chi tiết, phân loại học tập và giá bán của bộ thẻ đã xuất bản.'
                : 'Đóng gói và phát hành học liệu Flashcard của bạn tới cộng đồng người học toàn quốc. Hỗ trợ mọi môn học từ Ngoại ngữ, CNTT, Y dược tới Thường thức.'}
            </p>
          </div>

          <Button variant="outline" asChild className="h-9 px-3.5 text-xs font-semibold rounded-xl shrink-0 self-start sm:self-center">
            <Link to={isEditMode ? `/marketplace/decks/${deckItemId}` : "/marketplace/decks"}>
              {isEditMode ? 'Quay lại chi tiết' : 'Quay lại Marketplace'}
            </Link>
          </Button>
        </div>
      </div>

      {/* Wizard Stepper Progress Bar */}
      <div className="rounded-2xl border border-border/80 bg-card/90 p-1.5 sm:p-3 shadow-xs backdrop-blur-md">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-1.5 sm:gap-2">
          {WIZARD_STEPS.map((s) => {
            const StepIcon = s.icon
            const isActive = currentStep === s.id
            const isCompleted = currentStep > s.id
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goToStep(s.id)}
                className={`flex items-center gap-2 p-2 sm:p-3 rounded-xl text-left transition-all relative overflow-hidden select-none min-h-[46px] sm:min-h-[52px] ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-sm ring-2 ring-primary/20 font-bold scale-[1.01]'
                    : isCompleted
                      ? 'bg-muted/60 hover:bg-muted/90 text-foreground font-semibold border border-border/80 cursor-pointer'
                      : 'bg-muted/30 hover:bg-muted/60 text-muted-foreground font-medium border border-transparent cursor-pointer'
                }`}
              >
                <div
                  className={`w-6 h-6 sm:w-8 sm:h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-primary-foreground/20 text-primary-foreground'
                      : isCompleted
                        ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-3.5 h-3.5 sm:w-4 sm:h-4" /> : <StepIcon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[11px] sm:text-xs font-bold truncate">
                    B{s.id}: {s.title}
                  </div>
                  <div className={`text-[10px] hidden xs:block truncate ${isActive ? 'text-primary-foreground/80' : 'text-muted-foreground'}`}>
                    {s.sub}
                  </div>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.target as HTMLElement).tagName === 'INPUT') {
            e.preventDefault()
          }
        }}
        className="grid gap-6 lg:grid-cols-3 items-start"
      >
        {/* Active Step Content Card (2 spans) */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden min-h-[480px] flex flex-col justify-between">
            {/* Step Header */}
            <CardHeader className="p-4 sm:p-6 pb-4 border-b border-border/40 bg-muted/20">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-2.5">
                  <span className="flex items-center justify-center w-7 h-7 rounded-xl bg-foreground text-background text-xs font-bold shadow-2xs">
                    {currentStep}
                  </span>
                  <div>
                    <CardTitle className="text-base sm:text-lg font-bold">
                      {WIZARD_STEPS[currentStep - 1].title}
                    </CardTitle>
                    <CardDescription className="text-xs">
                      {WIZARD_STEPS[currentStep - 1].sub}
                    </CardDescription>
                  </div>
                </div>
                <Badge variant="secondary" className="text-xs font-semibold text-muted-foreground bg-muted/60 border-border/60 px-2.5 py-1 shrink-0">
                  Bước {currentStep} / 4
                </Badge>
              </div>
            </CardHeader>

            {/* Step Body */}
            <CardContent className="p-4 sm:p-6 space-y-5 flex-1">
              {currentStep === 1 && (
                <PublishStep1BasicInfo
                  isEditMode={isEditMode}
                  decks={decks}
                  sourceDeckId={sourceDeckId}
                  deckItem={deckItem}
                  title={title}
                  isTitleManuallyEdited={isTitleManuallyEdited}
                  previewText={previewText}
                  description={description}
                  tags={tags}
                  changelog={changelog}
                  isReleaseVersioned={isReleaseVersioned}
                  fieldErrors={fieldErrors}
                  setSourceDeckId={setSourceDeckId}
                  setTitle={setTitle}
                  setIsTitleManuallyEdited={setIsTitleManuallyEdited}
                  setPreviewText={setPreviewText}
                  setDescription={setDescription}
                  setTags={setTags}
                  setChangelog={setChangelog}
                  clearFieldError={clearFieldError}
                />
              )}

              {currentStep === 2 && (
                <PublishStep2Taxonomy
                  taxonomyDomain={taxonomyDomain}
                  taxonomySubject={taxonomySubject}
                  taxonomyFramework={taxonomyFramework}
                  taxonomyFrameworkLevel={taxonomyFrameworkLevel}
                  taxonomyDifficulty={taxonomyDifficulty}
                  subcategory={subcategory}
                  primaryCategory={primaryCategory}
                  customCategory={customCategory}
                  targetAudience={targetAudience}
                  fieldErrors={fieldErrors}
                  availableDomains={availableDomains}
                  availableSubjects={availableSubjects}
                  availableFrameworks={availableFrameworks}
                  activeFramework={activeFramework}
                  taxonomySchema={taxonomySchema}
                  setTaxonomyDomain={setTaxonomyDomain}
                  setTaxonomySubject={setTaxonomySubject}
                  setTaxonomyFramework={setTaxonomyFramework}
                  setTaxonomyFrameworkLevel={setTaxonomyFrameworkLevel}
                  setTaxonomyDifficulty={setTaxonomyDifficulty}
                  setSubcategory={setSubcategory}
                  setPrimaryCategory={setPrimaryCategory}
                  setCustomCategory={setCustomCategory}
                  setTargetAudience={setTargetAudience}
                  setTaxonomyGoals={setTaxonomyGoals}
                  setTaxonomyTopics={setTaxonomyTopics}
                  setTags={setTags}
                  clearFieldError={clearFieldError}
                />
              )}

              {currentStep === 3 && (
                <PublishStep3Goals
                  taxonomyDomain={taxonomyDomain}
                  taxonomySubject={taxonomySubject}
                  taxonomyGoals={taxonomyGoals}
                  taxonomyTopics={taxonomyTopics}
                  availableDomains={availableDomains}
                  availableSubjects={availableSubjects}
                  availableGoals={availableGoals}
                  availableTopics={availableTopics}
                  fieldErrors={fieldErrors}
                  setTaxonomyGoals={setTaxonomyGoals}
                  setTaxonomyTopics={setTaxonomyTopics}
                  clearFieldError={clearFieldError}
                />
              )}

              {currentStep === 4 && (
                <div className="space-y-5 animate-in fade-in duration-200">
                  <PublishStep4Pricing
                    distributionMode={distributionMode}
                    pricingMode={pricingMode}
                    priceAmountMinor={priceAmountMinor}
                    studentOfferMode={studentOfferMode}
                    studentDiscountPercent={studentDiscountPercent}
                    courseTitle={courseTitle}
                    courseDescription={courseDescription}
                    courseUrl={courseUrl}
                    courseInstructions={courseInstructions}
                    version={version}
                    isReleaseVersioned={isReleaseVersioned}
                    deckItemId={deckItemId}
                    fieldErrors={fieldErrors}
                    setDistributionMode={setDistributionMode}
                    setPricingMode={setPricingMode}
                    setPriceAmountMinor={setPriceAmountMinor}
                    setStudentOfferMode={setStudentOfferMode}
                    setStudentDiscountPercent={setStudentDiscountPercent}
                    setCourseTitle={setCourseTitle}
                    setCourseDescription={setCourseDescription}
                    setCourseUrl={setCourseUrl}
                    setCourseInstructions={setCourseInstructions}
                    setVersion={setVersion}
                    clearFieldError={clearFieldError}
                  />

                  {/* Summary Checklist before Submit */}
                  <div className="p-4 rounded-xl border border-border/80 bg-muted/30 space-y-2.5 text-xs">
                    <div className="font-bold text-foreground flex items-center gap-1.5">
                      <Sparkles className="w-4 h-4 text-muted-foreground" />
                      <span>Tóm tắt thông tin xuất bản:</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
                      <div>Tiêu đề: <strong className="text-foreground">{title || 'Chưa đặt'}</strong></div>
                      <div>Môn học: <strong className="text-foreground">{availableSubjects.find(s => s.id === taxonomySubject)?.label || taxonomySubject}</strong></div>
                      <div>Độ khó: <strong className="text-foreground">{TAXONOMY_DIFFICULTIES.find(d => d.id === taxonomyDifficulty)?.label || taxonomyDifficulty}</strong></div>
                      <div>
                        Mô hình:{' '}
                        <strong className="text-foreground">
                          {distributionMode === 'course_key'
                            ? 'Mã lớp học (Keys)'
                            : distributionMode === 'paid'
                              ? `${priceAmountMinor.toLocaleString('vi-VN')} đ`
                              : 'Miễn phí'}
                        </strong>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>

            {/* Step Navigation Actions Footer */}
            <div className="p-4 sm:p-6 border-t border-border/40 bg-muted/10 flex items-center justify-between gap-3">
              <Button
                type="button"
                variant="outline"
                size="default"
                onClick={handlePrevStep}
                disabled={currentStep === 1}
                className="h-11 sm:h-10 px-4 text-xs font-semibold rounded-xl shrink-0"
              >
                <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
                Quay lại
              </Button>

              <div className="text-xs text-muted-foreground font-medium hidden sm:block">
                Bước <strong className="text-foreground">{currentStep}</strong> / 4: {WIZARD_STEPS[currentStep - 1].title}
              </div>

              {currentStep < 4 ? (
                <Button
                  type="button"
                  size="default"
                  onClick={handleNextStep}
                  className="h-11 sm:h-10 px-5 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
                >
                  <span>Tiếp tục (Bước {currentStep + 1})</span>
                  <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
                </Button>
              ) : (
                <Button
                  type="button"
                  size="default"
                  onClick={handlePublish}
                  disabled={publishMutation.isPending}
                  className="h-11 sm:h-10 px-6 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-md hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
                >
                  <CheckCircle2 className="w-4 h-4 mr-1.5" />
                  <span>{publishMutation.isPending ? 'Đang lưu…' : isEditMode ? 'Cập nhật cấu hình chia sẻ' : 'Xuất bản Bộ thẻ ngay'}</span>
                </Button>
              )}
            </div>
          </Card>
        </div>

        {/* Sidebar Column: Live Preview & Progress Checklist (1 span) */}
        <div className="lg:col-span-1 space-y-6 lg:sticky lg:top-6 self-start">
          {/* Live Marketplace Card Preview */}
          <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-2 border-b border-border/40 bg-muted/20">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xs font-bold text-foreground uppercase tracking-wider flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-muted-foreground" />
                  <span>Xem trước Marketplace</span>
                </CardTitle>
                <Badge variant="secondary" className="text-[10px]">
                  Live Card
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 space-y-3">
              <div className="rounded-xl border bg-card/90 p-4 space-y-3 shadow-2xs">
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1 min-w-0">
                    <div className="font-bold text-sm text-foreground line-clamp-1">
                      {title.trim() || 'Tiêu đề Bộ thẻ của bạn'}
                    </div>
                    <div className="text-xs text-muted-foreground line-clamp-2">
                      {previewText.trim() || 'Mô tả ngắn hiển thị tại đây khi người học duyệt danh sách Marketplace...'}
                    </div>
                  </div>
                  <Badge
                    variant={
                      distributionMode === 'course_key'
                        ? 'outline'
                        : distributionMode === 'paid'
                          ? 'default'
                          : 'secondary'
                    }
                    className={`shrink-0 text-xs font-bold ${
                      distributionMode === 'course_key'
                        ? 'border-purple-500/30 text-purple-600 dark:text-purple-400 bg-purple-500/10'
                        : ''
                    }`}
                  >
                    {distributionMode === 'course_key'
                      ? 'Mã khóa học'
                      : distributionMode === 'paid'
                        ? `${priceAmountMinor.toLocaleString('vi-VN')} đ`
                        : 'Miễn phí'}
                  </Badge>
                </div>

                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <Badge variant="secondary" className="text-[10px] bg-muted/60 text-foreground border-border/60 font-semibold">
                    {effectiveCategory}
                  </Badge>
                  {selectedDeck ? (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground">
                      {selectedDeck.card_count} thẻ
                    </Badge>
                  ) : null}
                  <Badge variant="outline" className="text-[10px] text-muted-foreground font-mono">
                    v{version}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Step Progress Checklist (Desktop only - mobile already has top Stepper) */}
          <Card className="hidden lg:block shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden">
            <CardHeader className="p-4 sm:p-5 pb-3 border-b border-border/40 bg-muted/20">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Tiến trình hoàn thiện
              </CardTitle>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 space-y-2.5 text-xs">
              {WIZARD_STEPS.map((s) => {
                const isCurrent = currentStep === s.id
                const isDone = currentStep > s.id
                return (
                  <div
                    key={s.id}
                    onClick={() => goToStep(s.id)}
                    className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                      isCurrent
                        ? 'border-primary/50 bg-primary/5 font-semibold text-foreground ring-1 ring-primary/20'
                        : isDone
                          ? 'border-border/60 bg-card hover:bg-muted/40 font-medium text-muted-foreground'
                          : 'border-border/40 bg-muted/20 text-muted-foreground'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div
                        className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          isDone
                            ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                            : isCurrent
                              ? 'bg-primary/20 text-primary'
                              : 'bg-muted text-muted-foreground'
                        }`}
                      >
                        {isDone ? <Check className="w-3 h-3" /> : s.id}
                      </div>
                      <span>{s.title}</span>
                    </div>
                    {isDone && <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />}
                  </div>
                )
              })}
            </CardContent>
          </Card>
        </div>
      </form>
    </Page>
  )
}

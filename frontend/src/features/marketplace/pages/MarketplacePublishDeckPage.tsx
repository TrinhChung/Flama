import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArrowLeft,
  Check,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { loadDeckOptionsForPublish } from '../publishApi'
import { useTaxonomySchema } from '../hooks/useTaxonomySchema'
import {
  CATEGORY_PRESETS,
} from '../utils/publishTaxonomyConstants'
import { WIZARD_STEPS } from '../components/publish/PublishWizardTypes'
import { PublishStep1BasicInfo } from '../components/publish/PublishStep1BasicInfo'
import { PublishStep2Taxonomy } from '../components/publish/PublishStep2Taxonomy'
import { PublishStep3Goals } from '../components/publish/PublishStep3Goals'
import { PublishStep4Pricing } from '../components/publish/PublishStep4Pricing'
import { PublishDeckSummaryFooter } from '../components/publish/PublishDeckSummaryFooter'

export function MarketplacePublishDeckPage() {
  const { t } = useTranslation('marketplace')
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
        publish_status: isEditMode ? (deckItem?.publish_status || 'published') : 'published',
        ...releaseMetadata,
      })
    },
    onSuccess: (data: any) => {
      const publishedId = data?.deck_marketplace_item?.id || data?.shared_deck?.id || deckItemId
      toast.success(
        isEditMode
          ? t('publish_deck.toast_update_success', { defaultValue: 'Đã cập nhật thông tin bộ thẻ trên Marketplace!' })
          : t('publish_deck.toast_create_success', { defaultValue: 'Xuất bản bộ thẻ thành công! Bạn có thể quản lý release và phiên bản tại đây.' }),
      )
      if (publishedId) {
        navigate(`/marketplace/decks/${publishedId}`)
      } else {
        navigate('/marketplace/decks')
      }
    },
    onError: (err: any) => {
      toast.error(err?.message || t('publish_deck.toast_error', { defaultValue: 'Không thể đăng tải bộ thẻ. Vui lòng kiểm tra lại thông tin.' }))
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
        toast.error(t('publish_deck.toast_step_error', { defaultValue: `Vui lòng hoàn thành các thông tin bắt buộc tại Bước ${step}`, step }))
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
      toast.error(t('publish_deck.toast_check_info', { defaultValue: 'Vui lòng kiểm tra và điền đủ thông tin trước khi chuyển bước' }))
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
          toast.error(t('publish_deck.toast_finish_step_first', { defaultValue: `Vui lòng hoàn thiện Bước ${s} trước`, step: s }))
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
    return <PageLoading label={t('common.loading', { defaultValue: 'Đang tải dữ liệu...' })} />
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
    <Page className="space-y-6 relative px-3 sm:px-6 lg:px-8 py-4 sm:py-6 max-w-4xl mx-auto">
      <AmbientBackground intensity="subtle" />

      {/* Compact Header */}
      <div className="flex items-center justify-between gap-4 pt-1">
        <h1 className="text-lg sm:text-xl font-bold tracking-tight text-foreground">
          {isEditMode
            ? t('publish_deck.title_edit', { defaultValue: 'Chỉnh sửa thông tin Bộ thẻ' })
            : t('publish_deck.title_create', { defaultValue: 'Chia sẻ Bộ thẻ vào Marketplace' })}
        </h1>
        <Button variant="outline" size="sm" asChild className="h-8 px-3 text-xs font-semibold rounded-xl shrink-0">
          <Link to={isEditMode ? `/marketplace/decks/${deckItemId}` : "/marketplace/decks"}>
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            {isEditMode
              ? t('publish_deck.btn_back_detail', { defaultValue: 'Quay lại chi tiết' })
              : t('publish_deck.back_btn', { defaultValue: 'Quay lại Marketplace' })}
          </Link>
        </Button>
      </div>

      {/* Wizard Stepper Progress Bar */}
      <div className="rounded-2xl border border-border/80 bg-card/90 p-1.5 sm:p-2.5 shadow-xs backdrop-blur-md">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {WIZARD_STEPS.map((s) => {
            const isActive = currentStep === s.id
            const isCompleted = currentStep > s.id
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goToStep(s.id)}
                className={`flex items-center gap-2.5 p-2.5 sm:p-3 rounded-xl text-left transition-all relative overflow-hidden select-none min-h-[48px] sm:min-h-[52px] border ${
                  isActive
                    ? 'border-primary/60 bg-primary/5 text-foreground font-semibold ring-1 ring-primary/20 shadow-2xs'
                    : isCompleted
                      ? 'border-border/70 bg-card hover:bg-muted/40 text-foreground font-medium cursor-pointer'
                      : 'border-border/40 bg-muted/20 text-muted-foreground hover:bg-muted/30 font-medium cursor-pointer'
                }`}
              >
                <div
                  className={`w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-2xs'
                      : isCompleted
                        ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                        : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-3.5 h-3.5 stroke-[2.5]" /> : s.id}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold truncate">
                    {s.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate hidden sm:block">
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
        className="space-y-6"
      >
        <Card className="shadow-xs rounded-2xl border-border/80 bg-card/90 backdrop-blur-sm overflow-hidden min-h-[480px] flex flex-col justify-between">
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
              </div>
            )}
          </CardContent>

          <PublishDeckSummaryFooter
            currentStep={currentStep}
            title={title}
            taxonomySubject={taxonomySubject}
            taxonomyDifficulty={taxonomyDifficulty}
            distributionMode={distributionMode}
            priceAmountMinor={priceAmountMinor}
            availableSubjects={availableSubjects}
            isEditMode={isEditMode}
            isPending={publishMutation.isPending}
            onPrevStep={handlePrevStep}
            onNextStep={handleNextStep}
            onPublish={handlePublish}
          />
        </Card>
      </form>
    </Page>
  )
}


import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { ArrowLeft, Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { appApi } from '@/app/api'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

import { useTaxonomySchema } from '../hooks/useTaxonomySchema'
import {
  NOTE_TYPE_CATEGORY_PRESETS,
} from '../utils/publishTaxonomyConstants'
import { PublishNoteTypeStep1Basic } from '../components/publish-notetype/PublishNoteTypeStep1Basic'
import { PublishNoteTypeStep2Taxonomy } from '../components/publish-notetype/PublishNoteTypeStep2Taxonomy'
import { PublishNoteTypeStep3Goals } from '../components/publish-notetype/PublishNoteTypeStep3Goals'
import { PublishNoteTypeStep4Pricing } from '../components/publish-notetype/PublishNoteTypeStep4Pricing'
import { PublishNoteTypeSummaryFooter } from '../components/publish-notetype/PublishNoteTypeSummaryFooter'

const WIZARD_STEPS = [
  { id: 1, title: 'Mẫu thẻ & Mô tả', sub: 'Chọn NoteType và giới thiệu' },
  { id: 2, title: 'Phân loại & Trình độ', sub: 'Chứng chỉ & Môn học' },
  { id: 3, title: 'Mục tiêu & Kỹ năng', sub: 'Goals & Chủ đề trọng tâm' },
  { id: 4, title: 'Giá bán & Đăng tải', sub: 'Thiết lập giá và xuất bản' },
]

type SimpleNoteType = {
  id: string
  name: string
  field_count?: number
  publish_status?: string
  is_marketplace_install?: boolean
}

export function MarketplacePublishNoteTypePage() {
  const { t } = useTranslation('marketplace')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryParamId = searchParams.get('id') || ''
  const isEditMode = searchParams.get('edit') === '1'

  const [sourceNoteTypeId, setSourceNoteTypeId] = useState<string>(queryParamId)
  const [title, setTitle] = useState('')
  const [previewText, setPreviewText] = useState('')
  const [description, setDescription] = useState('')
  const [pricingMode, setPricingMode] = useState<'free' | 'paid'>('free')
  const [priceAmountMinor, setPriceAmountMinor] = useState<number>(10000)
  const [version, setVersion] = useState('1.0.0')
  const [tags, setTags] = useState('')
  const [changelog, setChangelog] = useState('')
  const [primaryCategory, setPrimaryCategory] = useState('Templates')
  const [customCategory, setCustomCategory] = useState('')

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

  const noteTypesQuery = useQuery({
    queryKey: ['my-note-types-for-publish'],
    queryFn: () => appApi.get<{ items: SimpleNoteType[] }>('/note-types'),
  })

  // Fetch detailed info of selected note type (fields & templates)
  const selectedNoteTypeDetailQuery = useQuery({
    queryKey: ['note-type-detail-publish', sourceNoteTypeId],
    queryFn: () => appApi.get<any>(`/api/note-types/${sourceNoteTypeId}`),
    enabled: Boolean(sourceNoteTypeId),
  })

  // Sync search param ID if passed in URL
  useEffect(() => {
    if (queryParamId && !sourceNoteTypeId) {
      setSourceNoteTypeId(queryParamId)
    }
  }, [queryParamId, sourceNoteTypeId])

  const noteTypes = noteTypesQuery.data?.items || []
  const selectedNoteType = noteTypes.find((nt) => nt.id === sourceNoteTypeId)
  const isSelectedInstalledCopy = Boolean(selectedNoteType?.is_marketplace_install)
  const isSelectedAlreadyPublished = Boolean(
    !isEditMode &&
    selectedNoteType && (
      selectedNoteType.publish_status === 'published'
      || selectedNoteType.publish_status === 'unlisted'
    )
  )
  const detailData = selectedNoteTypeDetailQuery.data

  const effectiveCategory = primaryCategory === 'Custom' ? customCategory.trim() || 'Khác' : primaryCategory

  // Auto set title if title is empty when selectedNoteType changes
  useEffect(() => {
    if (!isEditMode && selectedNoteType && !title) {
      setTitle(selectedNoteType.name)
    }
  }, [selectedNoteType, title, isEditMode])

  // Populate form states from edit data
  useEffect(() => {
    if (isEditMode && detailData) {
      setTitle(detailData.title || detailData.name || '')
      setPreviewText(detailData.preview_text || '')
      setDescription(detailData.description || '')
      setPricingMode(detailData.pricing_mode || 'free')
      setPriceAmountMinor(detailData.price_amount_minor || 10000)
      setVersion(detailData.version || '1.0.0')
      setTags(detailData.tags ? detailData.tags.join(', ') : '')
      setChangelog(detailData.changelog || '')
      
      const cat = detailData.primary_category || 'Templates'
      const noteTypeCategoryPresetsValues = NOTE_TYPE_CATEGORY_PRESETS.map(p => p.id)
      if (noteTypeCategoryPresetsValues.includes(cat)) {
        setPrimaryCategory(cat)
        setCustomCategory('')
      } else {
        setPrimaryCategory('Custom')
        setCustomCategory(cat)
      }

      setTaxonomyDomain(detailData.taxonomy_metadata?.domain || 'language_learning')
      setTaxonomySubject(detailData.taxonomy_metadata?.subject || 'japanese')
      setTaxonomyFramework(detailData.taxonomy_metadata?.framework || '')
      setTaxonomyFrameworkLevel(detailData.taxonomy_metadata?.framework_level || '')
      setTaxonomyDifficulty(detailData.taxonomy_metadata?.difficulty_band || 'beginner')
      setTaxonomyGoals(detailData.taxonomy_metadata?.learning_goals || ['vocabulary'])
      setTaxonomyTopics(detailData.taxonomy_metadata?.primary_topics || ['meaning_recall'])
    }
  }, [isEditMode, detailData])

  const publishMutation = useMutation({
    mutationFn: () =>
      appApi.mutate(`/api/note-types/${sourceNoteTypeId}/publish`, 'POST', {
        title: title.trim(),
        preview_text: previewText.trim(),
        description: description.trim(),
        pricing_mode: pricingMode,
        price_amount_minor: pricingMode === 'paid' ? priceAmountMinor : 0,
        version: version.trim() || '1.0.0',
        tags: tags ? tags.split(',').map((t) => t.trim()).filter(Boolean) : [],
        changelog: changelog.trim(),
        primary_category: effectiveCategory,
        taxonomy_domain: taxonomyDomain,
        taxonomy_subject: taxonomySubject,
        taxonomy_framework: taxonomyFramework || undefined,
        taxonomy_framework_level: taxonomyFrameworkLevel || undefined,
        taxonomy_difficulty_band: taxonomyDifficulty,
        taxonomy_learning_goals: taxonomyGoals,
        taxonomy_primary_topics: taxonomyTopics,
      }),
    onSuccess: () => {
      toast.success(
        isEditMode
          ? 'Đã cập nhật cấu hình chia sẻ Loại thẻ thành công!'
          : 'Đã xuất bản Loại thẻ lên Marketplace thành công!'
      )
      navigate(`/marketplace/note-types/${sourceNoteTypeId}`)
    },
    onError: (error: any) => {
      const msg = error?.message || ''
      const field = error?.field || ''
      const serverErrs: Record<string, string> = {}

      if (field === 'source_note_type_id' || msg.includes('source_note_type_id')) {
        serverErrs.sourceNoteTypeId = 'Vui lòng chọn loại thẻ cần xuất bản.'
      }
      if (field === 'title' || msg.includes('Title')) {
        serverErrs.title = 'Vui lòng nhập tiêu đề hiển thị.'
      }
      if (field === 'description' || msg.includes('Description')) {
        serverErrs.description = 'Vui lòng nhập mô tả chi tiết mẫu thẻ.'
      }
      if (field === 'preview_text' || msg.includes('Preview text')) {
        serverErrs.previewText = 'Vui lòng nhập xem trước ngắn (Preview Text).'
      }
      if (field === 'taxonomy_domain' || msg.includes('taxonomy_domain')) {
        serverErrs.taxonomyDomain = 'Vui lòng chọn Lĩnh vực học tập.'
      }
      if (field === 'taxonomy_subject' || msg.includes('taxonomy_subject')) {
        serverErrs.taxonomySubject = 'Vui lòng chọn Ngôn ngữ / Môn học.'
      }
      if (field === 'taxonomy_difficulty_band' || msg.includes('taxonomy_difficulty_band')) {
        serverErrs.taxonomyDifficulty = 'Vui lòng chọn Trình độ / Mức độ khó.'
      }
      if (field === 'taxonomy_learning_goals' || msg.includes('learning goal')) {
        serverErrs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập.'
      }
      if (field === 'taxonomy_primary_topics' || msg.includes('primary topic')) {
        serverErrs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính.'
      }

      if (Object.keys(serverErrs).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...serverErrs }))
        toast.error('Có thông tin bị thiếu hoặc không hợp lệ. Vui lòng kiểm tra các vị trí báo đỏ.')
      } else {
        toast.error(msg || 'Không thể xuất bản. Vui lòng kiểm tra lại thông tin.')
      }
    },
  })

  const validateStep = (stepNumber: number): boolean => {
    const errs: Record<string, string> = {}
    if (stepNumber === 1) {
      if (!isEditMode && !sourceNoteTypeId) {
        errs.sourceNoteTypeId = 'Vui lòng chọn Loại thẻ cần xuất bản.'
      }
      if (isSelectedInstalledCopy) {
        errs.sourceNoteTypeId = 'Loại thẻ tải từ Marketplace không thể chia sẻ lại.'
      }
      if (isSelectedAlreadyPublished) {
        errs.sourceNoteTypeId = 'Loại thẻ này đã xuất bản. Vui lòng bấm "Chỉnh sửa" thay vì xuất bản mới.'
      }
      if (!title.trim()) {
        errs.title = 'Vui lòng nhập tiêu đề hiển thị.'
      }
      if (!previewText.trim()) {
        errs.previewText = 'Vui lòng nhập đoạn tóm tắt xem trước.'
      }
      if (!description.trim()) {
        errs.description = 'Vui lòng nhập mô tả chi tiết.'
      }
    } else if (stepNumber === 2) {
      if (!taxonomyDomain) {
        errs.taxonomyDomain = 'Vui lòng chọn Lĩnh vực học tập.'
      }
      if (!taxonomySubject) {
        errs.taxonomySubject = 'Vui lòng chọn Ngôn ngữ / Môn học.'
      }
      if (!taxonomyDifficulty) {
        errs.taxonomyDifficulty = 'Vui lòng chọn Mức độ khó.'
      }
      if (primaryCategory === 'Custom' && !customCategory.trim()) {
        errs.customCategory = 'Vui lòng nhập tên danh mục tùy chỉnh.'
      }
    } else if (stepNumber === 3) {
      if (taxonomyGoals.length === 0) {
        errs.taxonomyGoals = 'Vui lòng chọn ít nhất 1 Mục tiêu học tập.'
      }
      if (taxonomyTopics.length === 0) {
        errs.taxonomyTopics = 'Vui lòng chọn ít nhất 1 Chủ đề chính.'
      }
    } else if (stepNumber === 4) {
      if (pricingMode === 'paid') {
        if (!priceAmountMinor || priceAmountMinor < 1000) {
          errs.priceAmountMinor = 'Giá bán tối thiểu là 1.000 VNĐ.'
        }
      }
    }

    setFieldErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleNextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep((prev) => Math.min(prev + 1, 4))
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      toast.error('Vui lòng hoàn thành các thông tin bắt buộc trước khi chuyển bước.')
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

  const handlePublish = () => {
    for (let s = 1; s <= 4; s++) {
      if (!validateStep(s)) {
        setCurrentStep(s)
        toast.error(`Thông tin tại Bước ${s} chưa đầy đủ. Vui lòng kiểm tra lại.`)
        return
      }
    }
    publishMutation.mutate()
  }

  const taxonomySchema = useTaxonomySchema('note_type')
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

  const fieldDefs = detailData?.fields || detailData?.field_definitions || []
  const templates = detailData?.templates || []

  if (noteTypesQuery.isPending || (sourceNoteTypeId && selectedNoteTypeDetailQuery.isPending)) {
    return <PageLoading label={t('common.loading', { defaultValue: 'Đang tải dữ liệu...' })} />
  }

  if (noteTypesQuery.error) {
    return (
      <Page>
        <PageError error={noteTypesQuery.error} />
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
            ? t('publish_notetype.title_edit', { defaultValue: 'Chỉnh sửa thông tin Mẫu Thẻ trên Marketplace' })
            : t('publish_notetype.title_create', { defaultValue: 'Chia sẻ Mẫu Thẻ (Note Type) vào Marketplace' })}
        </h1>
        <Button variant="outline" size="sm" asChild className="h-8 px-3 text-xs font-semibold rounded-xl shrink-0">
          <Link to="/marketplace/note-types">
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            {t('publish_notetype.back_btn', { defaultValue: 'Quay lại NoteTypes' })}
          </Link>
        </Button>
      </div>

      {/* Stepper Wizard Bar */}
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
          <CardContent className="p-4 sm:p-6 space-y-5 flex-1">
            {currentStep === 1 && (
              <PublishNoteTypeStep1Basic
                isEditMode={isEditMode}
                noteTypes={noteTypes}
                sourceNoteTypeId={sourceNoteTypeId}
                selectedNoteType={selectedNoteType}
                isSelectedInstalledCopy={isSelectedInstalledCopy}
                isSelectedAlreadyPublished={isSelectedAlreadyPublished}
                fieldDefs={fieldDefs}
                templates={templates}
                title={title}
                previewText={previewText}
                description={description}
                tags={tags}
                changelog={changelog}
                fieldErrors={fieldErrors}
                setSourceNoteTypeId={setSourceNoteTypeId}
                setTitle={setTitle}
                setPreviewText={setPreviewText}
                setDescription={setDescription}
                setTags={setTags}
                setChangelog={setChangelog}
                clearFieldError={clearFieldError}
              />
            )}

            {currentStep === 2 && (
              <PublishNoteTypeStep2Taxonomy
                taxonomyDomain={taxonomyDomain}
                taxonomySubject={taxonomySubject}
                taxonomyFramework={taxonomyFramework}
                taxonomyFrameworkLevel={taxonomyFrameworkLevel}
                taxonomyDifficulty={taxonomyDifficulty}
                primaryCategory={primaryCategory}
                customCategory={customCategory}
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
                setPrimaryCategory={setPrimaryCategory}
                setCustomCategory={setCustomCategory}
                setTaxonomyGoals={setTaxonomyGoals}
                setTaxonomyTopics={setTaxonomyTopics}
                setTags={setTags}
                clearFieldError={clearFieldError}
              />
            )}

            {currentStep === 3 && (
              <PublishNoteTypeStep3Goals
                taxonomyDomain={taxonomyDomain}
                taxonomySubject={taxonomySubject}
                taxonomyGoals={taxonomyGoals}
                taxonomyTopics={taxonomyTopics}
                fieldErrors={fieldErrors}
                availableDomains={availableDomains}
                availableSubjects={availableSubjects}
                availableGoals={availableGoals}
                availableTopics={availableTopics}
                setTaxonomyGoals={setTaxonomyGoals}
                setTaxonomyTopics={setTaxonomyTopics}
                clearFieldError={clearFieldError}
              />
            )}

            {currentStep === 4 && (
              <PublishNoteTypeStep4Pricing
                pricingMode={pricingMode}
                priceAmountMinor={priceAmountMinor}
                version={version}
                title={title}
                taxonomySubject={taxonomySubject}
                effectiveCategory={effectiveCategory}
                availableSubjects={availableSubjects}
                fieldErrors={fieldErrors}
                setPricingMode={setPricingMode}
                setPriceAmountMinor={setPriceAmountMinor}
                setVersion={setVersion}
                clearFieldError={clearFieldError}
              />
            )}
          </CardContent>

          <PublishNoteTypeSummaryFooter
            currentStep={currentStep}
            isEditMode={isEditMode}
            isPending={publishMutation.isPending}
            isSelectedInstalledCopy={isSelectedInstalledCopy}
            isSelectedAlreadyPublished={isSelectedAlreadyPublished}
            onPrevStep={handlePrevStep}
            onNextStep={handleNextStep}
            onPublish={handlePublish}
          />
        </Card>
      </form>
    </Page>
  )
}

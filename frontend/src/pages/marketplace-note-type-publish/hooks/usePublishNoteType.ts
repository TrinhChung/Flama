import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { useTaxonomySchema, NOTE_TYPE_CATEGORY_PRESETS } from '@/features/marketplace'
import { templateListingValidationError, TEMPLATE_MIN_PRICE, type TemplateListingDraft } from '@/entities/card-template'
import { publishNoteTypeApi, type PublishTemplateOption } from '../api/publishNoteTypeApi'

export function usePublishNoteType() {
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
    queryFn: () => publishNoteTypeApi.listNoteTypes(),
  })

  // Fetch detailed info of selected note type (fields & templates)
  const selectedNoteTypeDetailQuery = useQuery({
    queryKey: ['note-type-detail-publish', sourceNoteTypeId],
    queryFn: () => publishNoteTypeApi.detail(sourceNoteTypeId),
    enabled: Boolean(sourceNoteTypeId),
  })

  const templateOptionsQuery = useQuery({
    queryKey: ['note-type-publish-options', sourceNoteTypeId],
    queryFn: ({ signal }) => publishNoteTypeApi.options(sourceNoteTypeId, signal),
    enabled: Boolean(sourceNoteTypeId),
  })
  const templateOptions = templateOptionsQuery.data?.templates ?? []
  const [templateDrafts, setTemplateDrafts] = useState<Record<string, TemplateListingDraft>>({})
  const listingDraft = (item: PublishTemplateOption): TemplateListingDraft => templateDrafts[`${sourceNoteTypeId}:${item.template_id}`] ?? {
    description: item.description || '', primary_category: item.primary_category || '',
    pricing_mode: item.pricing_mode === 'paid' ? 'paid' : 'free', price_amount_minor: item.price_amount_minor || 0,
  }
  const updateListingDraft = (item: PublishTemplateOption, patch: Partial<TemplateListingDraft>) => {
    setTemplateDrafts((prev) => ({ ...prev, [`${sourceNoteTypeId}:${item.template_id}`]: { ...listingDraft(item), ...patch } }))
    clearFieldError(`template:${item.template_id}`)
  }

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
      publishNoteTypeApi.publish(sourceNoteTypeId, {
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
        template_listings: templateOptions.filter((item) => item.is_owned && item.requires_publication).map((item) => {
          const draft = listingDraft(item)
          return { template_id: item.template_id, ...draft, price_amount_minor: draft.pricing_mode === 'paid' ? draft.price_amount_minor : 0 }
        }),
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
        serverErrs.sourceNoteTypeId = 'Vui lòng chọn cấu trúc thẻ cần xuất bản.'
      }
      if (field === 'title' || msg.includes('Title')) {
        serverErrs.title = 'Vui lòng nhập tiêu đề hiển thị.'
      }
      if (field === 'description' || msg.includes('Description')) {
        serverErrs.description = 'Vui lòng nhập mô tả chi tiết cấu trúc thẻ.'
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
      if (templateOptionsQuery.isPending || templateOptionsQuery.error) {
        errs.templateListings = t('bundle.publish.options_required')
      }
      for (const item of templateOptions.filter((item) => item.is_owned && item.requires_publication)) {
        const error = templateListingValidationError(listingDraft(item))
        if (error) errs[`template:${item.template_id}`] = t(`templates.publish.error_${error}`, { min: TEMPLATE_MIN_PRICE.toLocaleString('vi-VN') })
      }
      if (pricingMode === 'paid') {
        if (!Number.isInteger(priceAmountMinor) || priceAmountMinor < 1000) {
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

  return { t, isEditMode, sourceNoteTypeId, setSourceNoteTypeId, title, setTitle, previewText, setPreviewText, description, setDescription, pricingMode, setPricingMode, priceAmountMinor, setPriceAmountMinor, version, setVersion, tags, setTags, changelog, setChangelog, primaryCategory, setPrimaryCategory, customCategory, setCustomCategory, taxonomyDomain, setTaxonomyDomain, taxonomySubject, setTaxonomySubject, taxonomyFramework, setTaxonomyFramework, taxonomyFrameworkLevel, setTaxonomyFrameworkLevel, taxonomyDifficulty, setTaxonomyDifficulty, taxonomyGoals, setTaxonomyGoals, taxonomyTopics, setTaxonomyTopics, currentStep, fieldErrors, clearFieldError, noteTypesQuery, selectedNoteTypeDetailQuery, noteTypes, selectedNoteType, isSelectedInstalledCopy, isSelectedAlreadyPublished, effectiveCategory, publishMutation, handleNextStep, handlePrevStep, goToStep, handlePublish, taxonomySchema, availableDomains, availableSubjects, availableFrameworks, activeFramework, availableGoals, availableTopics, fieldDefs, templates, templateOptionsQuery, templateOptions, listingDraft, updateListingDraft }
}

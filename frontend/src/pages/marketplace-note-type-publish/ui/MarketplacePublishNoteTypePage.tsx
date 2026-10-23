import { Link } from 'react-router-dom'
import { ArrowLeft, Check } from 'lucide-react'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

import { PublishNoteTypeStep1Basic } from './PublishNoteTypeStep1Basic'
import { PublishNoteTypeStep2Taxonomy } from './PublishNoteTypeStep2Taxonomy'
import { PublishNoteTypeStep3Goals } from './PublishNoteTypeStep3Goals'
import { PublishNoteTypeStep4Pricing } from './PublishNoteTypeStep4Pricing'
import { PublishNoteTypeSummaryFooter } from './PublishNoteTypeSummaryFooter'

import { usePublishNoteType } from '../hooks/usePublishNoteType'
import { PublishBundleTemplates } from './PublishBundleTemplates'

const WIZARD_STEPS = [
  { id: 1, title: 'Cấu trúc thẻ & Mô tả', sub: 'Chọn Cấu trúc thẻ và giới thiệu' },
  { id: 2, title: 'Phân loại & Trình độ', sub: 'Chứng chỉ & Môn học' },
  { id: 3, title: 'Mục tiêu & Kỹ năng', sub: 'Goals & Chủ đề trọng tâm' },
  { id: 4, title: 'Giá bán & Đăng tải', sub: 'Thiết lập giá và xuất bản' },
]

export function MarketplacePublishNoteTypePage() {
  const { t, isEditMode, sourceNoteTypeId, setSourceNoteTypeId, title, setTitle, previewText, setPreviewText, description, setDescription, pricingMode, setPricingMode, priceAmountMinor, setPriceAmountMinor, version, setVersion, tags, setTags, changelog, setChangelog, primaryCategory, setPrimaryCategory, customCategory, setCustomCategory, taxonomyDomain, setTaxonomyDomain, taxonomySubject, setTaxonomySubject, taxonomyFramework, setTaxonomyFramework, taxonomyFrameworkLevel, setTaxonomyFrameworkLevel, taxonomyDifficulty, setTaxonomyDifficulty, taxonomyGoals, setTaxonomyGoals, taxonomyTopics, setTaxonomyTopics, currentStep, fieldErrors, clearFieldError, noteTypesQuery, selectedNoteTypeDetailQuery, noteTypes, selectedNoteType, isSelectedInstalledCopy, isSelectedAlreadyPublished, effectiveCategory, publishMutation, handleNextStep, handlePrevStep, goToStep, handlePublish, taxonomySchema, availableDomains, availableSubjects, availableFrameworks, activeFramework, availableGoals, availableTopics, fieldDefs, templates, templateOptionsQuery, templateOptions, listingDraft, updateListingDraft } = usePublishNoteType()

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
            ? t('publish_notetype.title_edit', { defaultValue: 'Chỉnh sửa thông tin Cấu trúc thẻ trên Chợ' })
            : t('publish_notetype.title_create', { defaultValue: 'Đăng Cấu trúc thẻ lên Chợ' })}
        </h1>
        <Button variant="outline" size="sm" asChild className="h-8 px-3 text-xs font-semibold rounded-xl shrink-0">
          <Link to="/marketplace/note-types">
            <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
            {t('publish_notetype.back_btn', { defaultValue: 'Quay lại Cấu trúc thẻ' })}
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
              <div className="space-y-5">
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
              <PublishBundleTemplates options={templateOptions} query={templateOptionsQuery} listingDraft={listingDraft} updateListingDraft={updateListingDraft} fieldErrors={fieldErrors} disabled={publishMutation.isPending} bundleAmount={pricingMode === 'paid' ? priceAmountMinor : 0} />
              </div>
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

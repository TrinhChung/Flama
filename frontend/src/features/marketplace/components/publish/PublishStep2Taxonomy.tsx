import '@/shared/config/i18n'
import { Check } from 'lucide-react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faLayerGroup } from '@fortawesome/free-solid-svg-icons'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  CATEGORY_PRESETS,
  TAXONOMY_DIFFICULTIES,
  getDefaultGoalsForSubject,
  getDefaultTopicsForSubject,
} from '../../utils/publishTaxonomyConstants'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep2TaxonomyProps {
  taxonomyDomain: string
  taxonomySubject: string
  taxonomyFramework: string
  taxonomyFrameworkLevel: string
  taxonomyDifficulty: string
  subcategory: string
  primaryCategory: string
  customCategory: string
  targetAudience: string
  fieldErrors: Record<string, string>
  availableDomains: any[]
  availableSubjects: any[]
  availableFrameworks: any[]
  activeFramework: any
  taxonomySchema: any
  setTaxonomyDomain: (val: string) => void
  setTaxonomySubject: (val: string) => void
  setTaxonomyFramework: (val: string) => void
  setTaxonomyFrameworkLevel: (val: string) => void
  setTaxonomyDifficulty: (val: string) => void
  setSubcategory: (val: string) => void
  setPrimaryCategory: (val: string) => void
  setCustomCategory: (val: string) => void
  setTargetAudience: (val: string) => void
  setTaxonomyGoals: (goals: string[]) => void
  setTaxonomyTopics: (topics: string[]) => void
  setTags: React.Dispatch<React.SetStateAction<string>>
  clearFieldError: (name: string) => void
}

export function PublishStep2Taxonomy({
  taxonomyDomain,
  taxonomySubject,
  taxonomyFrameworkLevel,
  taxonomyDifficulty,
  subcategory,
  primaryCategory,
  customCategory,
  targetAudience,
  fieldErrors,
  availableDomains,
  availableSubjects,
  availableFrameworks,
  activeFramework,
  taxonomySchema,
  setTaxonomyDomain,
  setTaxonomySubject,
  setTaxonomyFramework,
  setTaxonomyFrameworkLevel,
  setTaxonomyDifficulty,
  setSubcategory,
  setPrimaryCategory,
  setCustomCategory,
  setTargetAudience,
  setTaxonomyGoals,
  setTaxonomyTopics,
  setTags,
  clearFieldError,
}: PublishStep2TaxonomyProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Domain & Subject in 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="tax-domain" className="text-xs font-semibold">
            {t('publish_deck.step2.domain_label')} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="tax-domain"
            value={taxonomyDomain}
            onChange={(e) => {
              const newDomain = e.target.value
              setTaxonomyDomain(newDomain)
              clearFieldError('taxonomyDomain')
              const subs = taxonomySchema.subjectsByDomain(newDomain)
              const newSub = subs.length > 0 ? subs[0].id : 'other'
              setTaxonomySubject(newSub)
              clearFieldError('taxonomySubject')

              const nextFrameworks = taxonomySchema.frameworksForSubject(newSub)
              if (nextFrameworks.length > 0) {
                setTaxonomyFramework(nextFrameworks[0].id)
                setTaxonomyFrameworkLevel('')
              } else {
                setTaxonomyFramework('')
                setTaxonomyFrameworkLevel('')
              }

              setTaxonomyGoals(getDefaultGoalsForSubject(newSub))
              setTaxonomyTopics(getDefaultTopicsForSubject(newSub))
            }}
            className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
              fieldErrors.taxonomyDomain ? 'border-destructive bg-destructive/5' : ''
            }`}
          >
            {availableDomains.map((d) => (
              <NativeSelectOption key={d.id} value={d.id}>
                {d.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldErrorMessage error={fieldErrors.taxonomyDomain} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="tax-subject" className="text-xs font-semibold">
            {t('publish_deck.step2.subject_label')} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="tax-subject"
            value={taxonomySubject}
            onChange={(e) => {
              const newSub = e.target.value
              setTaxonomySubject(newSub)
              clearFieldError('taxonomySubject')
              const nextFrameworks = taxonomySchema.frameworksForSubject(newSub)
              if (nextFrameworks.length > 0) {
                setTaxonomyFramework(nextFrameworks[0].id)
                setTaxonomyFrameworkLevel('')
              } else {
                setTaxonomyFramework('')
                setTaxonomyFrameworkLevel('')
              }

              setTaxonomyGoals(getDefaultGoalsForSubject(newSub))
              setTaxonomyTopics(getDefaultTopicsForSubject(newSub))
            }}
            className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
              fieldErrors.taxonomySubject ? 'border-destructive bg-destructive/5' : ''
            }`}
          >
            {availableSubjects.map((s) => (
              <NativeSelectOption key={s.id} value={s.id}>
                {s.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldErrorMessage error={fieldErrors.taxonomySubject} />
        </div>
      </div>

      {/* 1-Click Framework & Level Selection */}
      {availableFrameworks.length > 0 && (
        <div className="space-y-3.5 p-4 rounded-2xl bg-muted/30 border border-border/80">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="p-1 rounded-lg bg-muted text-muted-foreground">
                <FontAwesomeIcon icon={faLayerGroup} className="w-3.5 h-3.5" />
              </div>
              <div>
                <Label className="text-xs font-bold text-foreground">
                  Khung chứng chỉ & Trình độ (Chọn nhanh 1 chạm)
                </Label>
                <p className="text-[11px] text-muted-foreground">
                  Tự động điền độ khó và thẻ tìm kiếm
                </p>
              </div>
            </div>
            {taxonomyFrameworkLevel && (
              <button
                type="button"
                onClick={() => setTaxonomyFrameworkLevel('')}
                className="text-xs text-muted-foreground hover:text-foreground font-medium underline transition-colors"
              >
                Bỏ chọn
              </button>
            )}
          </div>

          {/* Framework Tabs */}
          {availableFrameworks.length > 1 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
              {availableFrameworks.map((fw) => {
                const isFwActive = activeFramework?.id === fw.id
                return (
                  <Button
                    key={fw.id}
                    type="button"
                    size="sm"
                    variant={isFwActive ? 'default' : 'outline'}
                    className={`h-8 px-3.5 text-xs rounded-xl font-semibold transition-all ${
                      isFwActive
                        ? 'bg-foreground text-background shadow-xs'
                        : 'bg-card hover:bg-muted text-muted-foreground'
                    }`}
                    onClick={() => setTaxonomyFramework(fw.id)}
                  >
                    {fw.label}
                  </Button>
                )
              })}
            </div>
          )}

          {/* Level Cards */}
          {activeFramework && (
            <div className="space-y-2 pt-1">
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {activeFramework.levels.map((lvl: any) => {
                  const isSelected = taxonomyFrameworkLevel === lvl.id
                  return (
                    <div
                      key={lvl.id}
                      onClick={() => {
                        setTaxonomyFramework(activeFramework.id)
                        setTaxonomyFrameworkLevel(lvl.id)
                        setTaxonomyDifficulty(lvl.difficulty_band)
                        clearFieldError('taxonomyDifficulty')

                        if (lvl.suggestedTags && lvl.suggestedTags.length > 0) {
                          setTags((prev) => {
                            const currentList = prev.split(',').map((t) => t.trim()).filter(Boolean)
                            const merged = Array.from(new Set([...currentList, ...(lvl.suggestedTags || [])]))
                            return merged.join(', ')
                          })
                        }
                      }}
                      className={`p-2.5 rounded-xl border text-xs font-medium cursor-pointer transition-all flex items-center justify-between select-none ${
                        isSelected
                          ? 'bg-card border-primary text-foreground font-bold shadow-xs ring-1 ring-primary/30 scale-[1.01]'
                          : 'bg-card hover:bg-muted/70 text-foreground border-border/80'
                      }`}
                    >
                      <span className="truncate">{lvl.label}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-primary shrink-0 ml-1" />}
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Difficulty & Subcategory in 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="tax-diff" className="text-xs font-semibold">
            {t('publish_deck.step2.difficulty_label')} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="tax-diff"
            value={taxonomyDifficulty}
            onChange={(e) => {
              setTaxonomyDifficulty(e.target.value)
              clearFieldError('taxonomyDifficulty')
            }}
            className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
              fieldErrors.taxonomyDifficulty ? 'border-destructive bg-destructive/5' : ''
            }`}
          >
            {TAXONOMY_DIFFICULTIES.map((d) => (
              <NativeSelectOption key={d.id} value={d.id}>
                {d.label}
              </NativeSelectOption>
            ))}
          </NativeSelect>
          <FieldErrorMessage error={fieldErrors.taxonomyDifficulty} />
        </div>

        <div className="space-y-2">
          <Label htmlFor="subcategory" className="text-xs font-semibold">
            Trình độ / Chứng chỉ chi tiết
          </Label>
          <Input
            id="subcategory"
            placeholder="Ví dụ: JLPT N3, HSK 4, IELTS 6.5, AWS SAA..."
            value={subcategory}
            onChange={(e) => setSubcategory(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl"
          />
        </div>
      </div>

      {/* Category Presets & Target Audience in 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="category" className="text-xs font-semibold">Danh mục Marketplace</Label>
          <NativeSelect
            id="category"
            value={primaryCategory}
            onChange={(e) => setPrimaryCategory(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl font-medium"
          >
            {CATEGORY_PRESETS.map((cat) => (
              <NativeSelectOption key={cat.id} value={cat.id}>
                {cat.label} — {cat.sub}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>

        <div className="space-y-2">
          <Label htmlFor="target_audience" className="text-xs font-semibold">Đối tượng người học phù hợp</Label>
          <Input
            id="target_audience"
            placeholder="Ví dụ: Người chuẩn bị thi JLPT N3, Kỹ sư IT..."
            value={targetAudience}
            onChange={(e) => setTargetAudience(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl"
          />
        </div>
      </div>

      {primaryCategory === 'Custom' && (
        <div className="space-y-1.5 animate-in fade-in duration-200">
          <Label htmlFor="custom-category" className="text-xs font-semibold">Tên danh mục tùy chỉnh <span className="text-destructive">*</span></Label>
          <Input
            id="custom-category"
            placeholder="Ví dụ: JLPT N2 Đọc hiểu, Tiếng Anh giao tiếp..."
            value={customCategory}
            onChange={(e) => {
              setCustomCategory(e.target.value)
              clearFieldError('customCategory')
            }}
            className={`h-10 text-xs sm:text-sm rounded-xl ${
              fieldErrors.customCategory ? 'border-destructive bg-destructive/5' : ''
            }`}
          />
          <FieldErrorMessage error={fieldErrors.customCategory} />
        </div>
      )}
    </div>
  )
}

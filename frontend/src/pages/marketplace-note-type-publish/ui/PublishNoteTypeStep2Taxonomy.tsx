import { AlertCircle, Check } from 'lucide-react'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faLayerGroup } from '@fortawesome/free-solid-svg-icons'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  NOTE_TYPE_CATEGORY_PRESETS,
  TAXONOMY_DIFFICULTIES,
  getDefaultGoalsForSubject,
  getDefaultTopicsForSubject,
} from '@/features/marketplace'

interface PublishNoteTypeStep2TaxonomyProps {
  taxonomyDomain: string
  taxonomySubject: string
  taxonomyFramework: string
  taxonomyFrameworkLevel: string
  taxonomyDifficulty: string
  primaryCategory: string
  customCategory: string
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
  setPrimaryCategory: (val: string) => void
  setCustomCategory: (val: string) => void
  setTaxonomyGoals: (val: string[]) => void
  setTaxonomyTopics: (val: string[]) => void
  setTags: React.Dispatch<React.SetStateAction<string>>
  clearFieldError: (name: string) => void
}

function FieldErrorMessage({ error }: { error?: string }) {
  if (!error) return null
  return (
    <p className="text-xs font-semibold text-destructive mt-1.5 flex items-center gap-1.5 animate-in fade-in">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
      <span>{error}</span>
    </p>
  )
}

export function PublishNoteTypeStep2Taxonomy({
  taxonomyDomain,
  taxonomySubject,
  taxonomyFramework: _taxonomyFramework,
  taxonomyFrameworkLevel,
  taxonomyDifficulty,
  primaryCategory,
  customCategory,
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
  setPrimaryCategory,
  setCustomCategory,
  setTaxonomyGoals,
  setTaxonomyTopics,
  setTags,
  clearFieldError,
}: PublishNoteTypeStep2TaxonomyProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Domain & Subject in 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="nt-tax-domain" className="text-xs font-semibold">
            {t('publish_deck.step2.domain_label', { defaultValue: 'Lĩnh vực học tập (Domain)' })} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="nt-tax-domain"
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
          <Label htmlFor="nt-tax-subject" className="text-xs font-semibold">
            {t('publish_deck.step2.subject_label', { defaultValue: 'Ngôn ngữ / Môn học (Subject)' })} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="nt-tax-subject"
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

      {/* Difficulty & Category in 2 columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="nt-tax-diff" className="text-xs font-semibold">
            {t('publish_deck.step2.difficulty_label', { defaultValue: 'Mức độ khó (Difficulty)' })} <span className="text-destructive">*</span>
          </Label>
          <NativeSelect
            id="nt-tax-diff"
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
          <Label htmlFor="nt-category" className="text-xs font-semibold">
            Danh mục cấu trúc thẻ
          </Label>
          <NativeSelect
            id="nt-category"
            value={primaryCategory}
            onChange={(e) => setPrimaryCategory(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl font-medium"
          >
            {NOTE_TYPE_CATEGORY_PRESETS.map((cat) => (
              <NativeSelectOption key={cat.id} value={cat.id}>
                {cat.label} — {cat.sub}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </div>
      </div>

      {primaryCategory === 'Custom' && (
        <div className="space-y-1.5 animate-in fade-in duration-200">
          <Label htmlFor="custom-category" className="text-xs font-semibold">
            Tên danh mục tùy chỉnh <span className="text-destructive">*</span>
          </Label>
          <Input
            id="custom-category"
            placeholder="Ví dụ: Lập trình Python, Kanji nâng cao..."
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

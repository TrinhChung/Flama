import { CheckCircle2, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep3GoalsProps {
  taxonomyDomain: string
  taxonomySubject: string
  taxonomyGoals: string[]
  taxonomyTopics: string[]
  availableDomains: any[]
  availableSubjects: any[]
  availableGoals: any[]
  availableTopics: any[]
  fieldErrors: Record<string, string>
  setTaxonomyGoals: React.Dispatch<React.SetStateAction<string[]>>
  setTaxonomyTopics: React.Dispatch<React.SetStateAction<string[]>>
  clearFieldError: (name: string) => void
}

export function PublishStep3Goals({
  taxonomyDomain,
  taxonomySubject,
  taxonomyGoals,
  taxonomyTopics,
  availableDomains,
  availableSubjects,
  availableGoals,
  availableTopics,
  fieldErrors,
  setTaxonomyGoals,
  setTaxonomyTopics,
  clearFieldError,
}: PublishStep3GoalsProps) {
  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      {/* Contextual Subject Banner */}
      <div className="flex items-center justify-between p-3.5 rounded-xl border border-border/80 bg-muted/30 text-xs">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-muted-foreground shrink-0" />
          <div>
            <span className="text-muted-foreground">Môn học đang chọn: </span>
            <strong className="text-foreground">
              {availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}
            </strong>
          </div>
        </div>
        <Badge variant="secondary" className="text-[10px] bg-card border-border/80 text-foreground font-semibold">
          {availableDomains.find((d) => d.id === taxonomyDomain)?.label.split('(')[0].trim() || 'Lĩnh vực'}
        </Badge>
      </div>

      {/* Learning Goals */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <div>
            <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <span>Mục tiêu học tập (Learning Goals)</span>
              <span className="text-destructive">*</span>
            </Label>
            <p className="text-[11px] text-muted-foreground">
              Chọn các mục tiêu người học sẽ đạt được khi học bộ thẻ này
            </p>
          </div>
          <Badge variant="secondary" className="text-[10px] font-mono shrink-0">
            Đã chọn: {taxonomyGoals.length}
          </Badge>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {availableGoals.map((g) => {
            const isSelected = taxonomyGoals.includes(g.id)
            return (
              <div
                key={g.id}
                onClick={() => {
                  clearFieldError('taxonomyGoals')
                  setTaxonomyGoals((prev) =>
                    isSelected ? prev.filter((id) => id !== g.id) : [...prev, g.id]
                  )
                }}
                className={`p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-1 min-h-[56px] ${
                  isSelected
                    ? 'bg-card border-primary text-foreground font-semibold shadow-xs ring-1 ring-primary/30'
                    : 'bg-card border-border/70 text-muted-foreground hover:text-foreground hover:border-border hover:bg-muted/30'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold leading-tight text-foreground">{g.label}</span>
                  {isSelected ? (
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-border shrink-0" />
                  )}
                </div>
                {g.sub && (
                  <span className="text-[10px] font-normal leading-tight text-muted-foreground">
                    {g.sub}
                  </span>
                )}
              </div>
            )
          })}
        </div>
        <FieldErrorMessage error={fieldErrors.taxonomyGoals} />
      </div>

      {/* Primary Topics */}
      <div className="space-y-2.5 pt-4 border-t border-border/40">
        <div className="flex items-center justify-between">
          <div>
            <Label className="text-xs font-bold text-foreground flex items-center gap-1.5">
              <span>Chủ đề chính liên kết (Primary Topics)</span>
              <span className="text-destructive">*</span>
            </Label>
            <p className="text-[11px] text-muted-foreground">
              Chủ đề được tối ưu hóa riêng theo môn học <strong>{availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}</strong>
            </p>
          </div>
          <Badge variant="secondary" className="text-[10px] font-mono shrink-0">
            Đã chọn: {taxonomyTopics.length}
          </Badge>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {availableTopics.map((t) => {
            const isSelected = taxonomyTopics.includes(t.id)
            return (
              <div
                key={t.id}
                onClick={() => {
                  clearFieldError('taxonomyTopics')
                  setTaxonomyTopics((prev) =>
                    isSelected ? prev.filter((id) => id !== t.id) : [...prev, t.id]
                  )
                }}
                className={`p-3 rounded-xl border transition-all cursor-pointer select-none flex flex-col justify-between gap-1 min-h-[56px] ${
                  isSelected
                    ? 'bg-card border-primary text-foreground font-semibold shadow-xs ring-1 ring-primary/30'
                    : 'bg-card border-border/70 text-muted-foreground hover:text-foreground hover:border-border hover:bg-muted/30'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold leading-tight text-foreground">{t.label}</span>
                  {isSelected ? (
                    <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                  ) : (
                    <div className="w-4 h-4 rounded-full border border-border shrink-0" />
                  )}
                </div>
                {t.sub && (
                  <span className="text-[10px] font-normal leading-tight text-muted-foreground">
                    {t.sub}
                  </span>
                )}
              </div>
            )
          })}
        </div>
        <FieldErrorMessage error={fieldErrors.taxonomyTopics} />
      </div>
    </div>
  )
}

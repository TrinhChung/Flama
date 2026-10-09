import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Check,
  ExternalLink,
  ListFilter,
  Settings2,
  SlidersHorizontal,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { PageError } from '@/shared/components/PageState'
import { AmbientBackground } from '@/components/ambient-background'
import type {
  StudyTemplateComposition,
  StudyTemplateFieldDef,
  StudyTemplatePreparationState,
} from '../hooks/useStudyTemplatePreparation'
import type { TemplateBindings, TemplateInputSpec } from '@/entities/card-template'

export type StudyTemplatePreparationProps = {
  preparation: StudyTemplatePreparationState
  deckName?: string | null
  error?: unknown
  disabled?: boolean
  onStart: () => void
}

type SelectInputsDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  inputSchema: TemplateInputSpec[]
  fieldDefs: StudyTemplateFieldDef[]
  value: TemplateBindings
  defaultBindings: TemplateBindings
  onChange: (value: TemplateBindings) => void
  disabled?: boolean
}

function SelectInputsDialog({
  open,
  onOpenChange,
  inputSchema,
  fieldDefs,
  value,
  defaultBindings,
  onChange,
  disabled = false,
}: SelectInputsDialogProps) {
  const baseId = useId()

  const handleSelectAll = () => {
    const updated: TemplateBindings = {}
    for (const input of inputSchema) {
      const candidates = fieldDefs.filter((f) => f.id && f.field_type === input.type)
      updated[input.key] =
        value[input.key] || defaultBindings[input.key] || candidates[0]?.id || null
    }
    onChange(updated)
  }

  const handleDeselectAll = () => {
    const updated: TemplateBindings = {}
    for (const input of inputSchema) {
      updated[input.key] = null
    }
    onChange(updated)
  }

  const handleToggleInput = (inputKey: string, inputType: string, checked: boolean) => {
    if (checked) {
      const candidates = fieldDefs.filter((f) => f.id && f.field_type === inputType)
      const target = defaultBindings[inputKey] || candidates[0]?.id || null
      onChange({ ...value, [inputKey]: target })
    } else {
      onChange({ ...value, [inputKey]: null })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[calc(100vw-2rem)] max-w-lg sm:max-w-xl max-h-[85dvh] flex flex-col gap-0 p-0 overflow-hidden rounded-2xl border-border/40 shadow-2xl">
        <DialogHeader className="p-4 sm:p-5 pb-3 border-b border-border/25">
          <DialogTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
            <SlidersHorizontal className="size-4.5 sm:size-5 text-primary shrink-0" />
            <span>Chọn các trường truyền vào template</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-1">
            Chọn những trường sẽ truyền dữ liệu vào template cho phiên học này. Nếu bỏ chọn, template sẽ nhận giá trị null.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2 sm:px-5 sm:py-2.5 bg-muted/20 border-b border-border/25 text-xs">
          <span className="text-muted-foreground font-medium">
            Tổng cộng: {inputSchema.length} trường
          </span>
          <div className="flex items-center gap-1.5 sm:gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={disabled}
              className="h-7 text-xs px-2 text-primary hover:text-primary cursor-pointer"
              onClick={handleSelectAll}
            >
              Chọn tất cả
            </Button>
            <span className="text-muted-foreground/40">|</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={disabled}
              className="h-7 text-xs px-2 text-muted-foreground hover:text-foreground cursor-pointer"
              onClick={handleDeselectAll}
            >
              Không truyền trường nào
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3.5 sm:p-5 space-y-2.5 sm:space-y-3">
          {inputSchema.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              Template này không yêu cầu trường đầu vào nào.
            </div>
          ) : (
            inputSchema.map((input, index) => {
              const inputId = `${baseId}-${index}`
              const candidates = fieldDefs.filter((f) => f.id && f.field_type === input.type)
              const mappedFieldId = value[input.key] || defaultBindings[input.key] || candidates[0]?.id
              const mappedField = fieldDefs.find((f) => f.id === mappedFieldId)
              const currentVal = value[input.key]
              const isTransmitted = currentVal !== null && currentVal !== undefined && currentVal !== ''
              const isStale = Boolean(isTransmitted && !candidates.some((f) => f.id === currentVal))

              return (
                <div
                  key={input.key}
                  className={`rounded-xl border p-3 sm:p-3.5 transition-all ${
                    isTransmitted
                      ? 'border-border/40 bg-card shadow-xs'
                      : 'border-border/20 bg-muted/20 opacity-75'
                  }`}
                >
                  <label
                    htmlFor={`${inputId}-checkbox`}
                    className="flex items-start gap-2.5 sm:gap-3 cursor-pointer select-none"
                  >
                    <input
                      id={`${inputId}-checkbox`}
                      type="checkbox"
                      checked={isTransmitted}
                      disabled={disabled}
                      className="mt-0.5 sm:mt-1 size-4 rounded border-border/50 text-primary focus:ring-primary cursor-pointer shrink-0"
                      onChange={(e) =>
                        handleToggleInput(input.key, input.type, e.target.checked)
                      }
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap justify-between">
                        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap min-w-0">
                          <span className="text-xs sm:text-sm font-semibold text-foreground truncate">
                            {input.label || input.key}
                          </span>
                          {input.label && input.label !== input.key && (
                            <span className="text-[11px] sm:text-xs text-muted-foreground font-mono">
                              ({input.key})
                            </span>
                          )}
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 uppercase shrink-0">
                            {input.type}
                          </Badge>
                          {input.required && (
                            <span className="text-[10px] sm:text-[11px] text-amber-600 dark:text-amber-400 font-medium shrink-0">
                              (Khuyến nghị)
                            </span>
                          )}
                        </div>

                        {isTransmitted ? (
                          <Badge
                            variant="secondary"
                            className="text-[10px] sm:text-[11px] font-medium bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20 shrink-0"
                          >
                            Được truyền
                          </Badge>
                        ) : (
                          <Badge
                            variant="secondary"
                            className="text-[10px] sm:text-[11px] text-muted-foreground shrink-0 font-mono bg-muted"
                          >
                            null (Không truyền)
                          </Badge>
                        )}
                      </div>

                      <div className="text-[11px] sm:text-xs text-muted-foreground mt-1 flex items-center gap-1.5 flex-wrap">
                        {isTransmitted ? (
                          <span>
                            Dữ liệu nguồn: <strong className="text-foreground">{mappedField?.name || 'Trường mặc định'}</strong>
                          </span>
                        ) : (
                          <span>Không truyền trường này, template sẽ nhận giá trị null</span>
                        )}
                      </div>

                      {isStale && (
                        <p
                          role="status"
                          className="mt-1.5 text-xs text-amber-700 dark:text-amber-400 font-medium"
                        >
                          Trường đã lưu không còn phù hợp. Hãy bỏ chọn để truyền null.
                        </p>
                      )}
                    </div>
                  </label>
                </div>
              )
            })
          )}
        </div>

        <DialogFooter className="p-3.5 sm:p-4 border-t border-border/25 bg-muted/15 sm:justify-end">
          <Button onClick={() => onOpenChange(false)} className="w-full sm:w-auto rounded-xl">
            <Check className="mr-1.5 size-4" />
            Xác nhận
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function StudyTemplatePreparation({
  preparation,
  deckName,
  error,
  disabled = false,
  onStart,
}: StudyTemplatePreparationProps) {
  const [fieldSelectionOpen, setFieldSelectionOpen] = useState(false)
  const pending = disabled || preparation.isSaving || preparation.isLoading
  const choices = preparation.availability?.compositions ?? []

  const selectedChoice = choices.find(
    (choice: StudyTemplateComposition) => choice.composition_id === preparation.compositionId,
  )

  const noteTypeId = selectedChoice?.note_type_id
  const targetApplicationId =
    selectedChoice?.study_application_id ||
    selectedChoice?.composition_id.match(/:application:([^:]+)/)?.[1] ||
    (selectedChoice?.application_id && !selectedChoice.application_id.startsWith('comp:')
      ? selectedChoice.application_id
      : null) ||
    selectedChoice?.template_id ||
    null

  const mappingUrl = noteTypeId
    ? targetApplicationId
      ? `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates/${encodeURIComponent(targetApplicationId)}`
      : `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/templates`
    : null

  const inputSchema = preparation.entry?.input_schema ?? []
  const totalInputs = inputSchema.length
  const transmittedCount = inputSchema.filter((input) => {
    const val = preparation.inputBindings[input.key]
    return val !== null && val !== undefined && val !== ''
  }).length

  return (
    <div className="relative flex min-h-[100dvh] w-full items-center justify-center overflow-y-auto p-3.5 sm:p-6 text-foreground">
      <AmbientBackground />
      <main className="relative z-10 w-full max-w-2xl rounded-3xl border border-border/40 bg-card/90 backdrop-blur-md p-5 sm:p-8 shadow-2xl shadow-primary/5 dark:shadow-none">
        {/* Nút quay về Dashboard ở đầu màn hình */}
        <div className="flex items-center justify-between pb-3.5 mb-5 border-b border-border/25">
          <Button
            asChild
            variant="ghost"
            size="sm"
            className="-ml-2 rounded-full text-xs sm:text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <Link to="/dashboard">
              <ArrowLeft className="mr-1.5 size-4 shrink-0" /> Quay về Dashboard
            </Link>
          </Button>
          <span className="text-[11px] sm:text-xs text-muted-foreground/80 font-medium px-2.5 py-1 rounded-full bg-muted/40">
            Phiên học Flashcard
          </span>
        </div>

        <div className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">Chuẩn bị phiên học</h1>
          {deckName ? <p className="text-xs sm:text-sm text-muted-foreground">{deckName}</p> : null}
        </div>

        {preparation.error || error ? (
          <div className="mt-4">
            <PageError error={preparation.error || error} />
          </div>
        ) : null}

        <div className="mt-5 sm:mt-6 space-y-4 sm:space-y-5">
          {/* Chọn Template cho phiên học */}
          <div className="space-y-1.5">
            <label htmlFor="study-template-choice" className="block text-xs sm:text-sm font-medium text-foreground">
              Template cho phiên này
            </label>
            <select
              id="study-template-choice"
              value={preparation.compositionId ?? ''}
              disabled={pending}
              className="h-10 sm:h-11 w-full rounded-xl border border-border/40 bg-muted/30 px-3.5 text-xs sm:text-sm text-foreground transition-all focus:border-primary/50 focus:bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:opacity-50"
              onChange={(event) => preparation.selectComposition(event.target.value)}
            >
              <option value="" disabled>
                Chọn template
              </option>
              {choices.map((choice: StudyTemplateComposition) => (
                <option key={choice.composition_id} value={choice.composition_id}>
                  {choice.note_type_name ? `${choice.note_type_name} · ` : ''}
                  {choice.template_name}
                </option>
              ))}
            </select>
          </div>

          {/* Phần tùy chọn truyền trường và mapping */}
          {preparation.entry && (
            <div className="space-y-3.5 rounded-2xl border border-border/30 bg-muted/30 dark:bg-muted/15 p-4 sm:p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-xs sm:text-sm font-semibold text-foreground">
                    Dữ liệu truyền vào template
                  </h2>
                  <p className="text-[11px] sm:text-xs text-muted-foreground mt-0.5">
                    Chọn các trường sẽ truyền vào hoặc thiết lập mapping cấu trúc Note Type.
                  </p>
                </div>
                {totalInputs > 0 && (
                  <Badge
                    variant={transmittedCount > 0 ? 'secondary' : 'outline'}
                    className="text-[11px] sm:text-xs shrink-0 rounded-full font-medium"
                  >
                    {transmittedCount}/{totalInputs} trường được truyền
                  </Badge>
                )}
              </div>

              {preparation.staleInputs.length > 0 && (
                <p role="status" className="text-xs text-amber-700 dark:text-amber-400 font-medium">
                  Trường đã lưu không còn phù hợp. Hãy kiểm tra lại hoặc bỏ chọn để truyền null.
                </p>
              )}

              {/* 2 nút thao tác chính theo yêu cầu */}
              <div className="grid gap-2.5 sm:grid-cols-2 pt-1">
                {/* Nút 1: Chọn các trường sẽ truyền vào */}
                <Button
                  type="button"
                  variant="outline"
                  disabled={pending}
                  className="w-full justify-start h-auto py-2.5 px-3.5 rounded-xl border-border/40 bg-card hover:bg-card hover:border-primary/40 hover:shadow-xs transition-all cursor-pointer"
                  onClick={() => setFieldSelectionOpen(true)}
                >
                  <ListFilter className="mr-2.5 size-4 text-primary shrink-0" />
                  <div className="text-left flex-1 min-w-0">
                    <div className="text-xs font-semibold">Chọn các trường truyền vào</div>
                    <div className="text-[11px] text-muted-foreground font-normal truncate">
                      {totalInputs === 0
                        ? 'Không yêu cầu input'
                        : transmittedCount === totalInputs
                        ? 'Đang truyền tất cả trường'
                        : `Đang truyền ${transmittedCount}/${totalInputs} (${totalInputs - transmittedCount} nhận null)`}
                    </div>
                  </div>
                </Button>

                {/* Nút 2: Thiết lập mapping của note type đến template */}
                {mappingUrl ? (
                  <Button
                    asChild
                    variant="outline"
                    className="w-full justify-start h-auto py-2.5 px-3.5 rounded-xl border-border/40 bg-card hover:bg-card hover:border-primary/40 hover:shadow-xs transition-all cursor-pointer"
                  >
                    <Link to={mappingUrl} target="_blank" rel="noopener noreferrer">
                      <Settings2 className="mr-2.5 size-4 text-primary shrink-0" />
                      <div className="text-left flex-1 min-w-0">
                        <div className="text-xs font-semibold flex items-center justify-between">
                          <span>Thiết lập mapping Note Type</span>
                          <ExternalLink className="size-3 text-muted-foreground ml-1 inline" />
                        </div>
                        <div className="text-[11px] text-muted-foreground font-normal truncate">
                          Đến cấu hình mapping Note Type
                        </div>
                      </div>
                    </Link>
                  </Button>
                ) : (
                  <Button
                    type="button"
                    variant="outline"
                    disabled
                    className="w-full justify-start h-auto py-2.5 px-3.5 rounded-xl border-border/40 opacity-60"
                  >
                    <Settings2 className="mr-2.5 size-4 text-muted-foreground shrink-0" />
                    <div className="text-left">
                      <div className="text-xs font-semibold">Thiết lập mapping Note Type</div>
                      <div className="text-[11px] text-muted-foreground font-normal">
                        Chưa chọn Note Type
                      </div>
                    </div>
                  </Button>
                )}
              </div>
            </div>
          )}

          {/* Tùy chọn ghi nhớ */}
          <div className="space-y-3 border-t border-border/25 pt-4 sm:pt-5">
            <label className="flex items-center gap-2.5 text-xs sm:text-sm cursor-pointer select-none group">
              <input
                type="checkbox"
                checked={preparation.remember}
                disabled={pending}
                className="size-4 rounded border-border/50 text-primary focus:ring-primary/30 cursor-pointer shrink-0 transition-colors"
                onChange={(event) => preparation.setRemember(event.target.checked)}
              />
              <span className="text-foreground/90 group-hover:text-foreground transition-colors">
                Ghi nhớ cho bộ thẻ này
              </span>
            </label>
            <label className="flex items-center gap-2.5 text-xs sm:text-sm cursor-pointer select-none group">
              <input
                type="checkbox"
                checked={preparation.askBeforeStudy}
                disabled={pending || !preparation.remember}
                className="size-4 rounded border-border/50 text-primary focus:ring-primary/30 cursor-pointer shrink-0 transition-colors"
                onChange={(event) => preparation.setAskBeforeStudy(event.target.checked)}
              />
              <span className="text-foreground/90 group-hover:text-foreground transition-colors">
                Luôn hỏi trước khi học
              </span>
            </label>
          </div>

          {/* Nút hành động ở cuối - bỏ nút quay về dashboard thừa */}
          <div className="flex items-center justify-end pt-5 sm:pt-6 border-t border-border/25">
            <Button
              size="lg"
              disabled={pending || !preparation.compositionId}
              onClick={onStart}
              className="w-full sm:w-auto min-w-36 h-11 px-6 rounded-xl bg-primary hover:bg-primary/90 text-primary-foreground font-semibold shadow-md shadow-primary/15 transition-all cursor-pointer"
            >
              {preparation.error || error ? 'Thử lại' : 'Bắt đầu học'}
            </Button>
          </div>
        </div>
      </main>

      {/* Dialog chọn các trường truyền vào */}
      {preparation.entry && (
        <SelectInputsDialog
          open={fieldSelectionOpen}
          onOpenChange={setFieldSelectionOpen}
          inputSchema={preparation.entry.input_schema}
          fieldDefs={preparation.entry.field_defs}
          value={preparation.inputBindings}
          defaultBindings={preparation.entry.input_bindings}
          onChange={preparation.changeBindings}
          disabled={pending}
        />
      )}
    </div>
  )
}

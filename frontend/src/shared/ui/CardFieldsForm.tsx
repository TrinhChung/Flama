import * as React from "react"
import { cva } from "class-variance-authority"
import { Volume2, Eye, EyeOff, Plus, X } from "lucide-react"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"

export const cardFieldLabelVariants = cva(
  "text-xs font-semibold uppercase tracking-wide flex items-center justify-between select-none",
  {
    variants: {
      hasError: {
        true: "text-destructive font-bold",
        false: "text-muted-foreground",
      },
    },
    defaultVariants: {
      hasError: false,
    },
  }
)

export const cardFieldInputVariants = cva(
  "w-full rounded-lg border text-xs sm:text-sm text-foreground transition-colors outline-none focus-visible:ring-2 focus-visible:ring-primary bg-muted/50 focus-visible:bg-background disabled:opacity-50 disabled:cursor-not-allowed",
  {
    variants: {
      hasError: {
        true: "border-destructive focus-visible:ring-destructive",
        false: "border-input hover:border-border",
      },
      size: {
        sm: "h-8 px-2.5",
        md: "h-9 px-3",
      },
    },
    defaultVariants: {
      hasError: false,
      size: "md",
    },
  }
)

export interface CardFieldDef {
  /** Field name identifier (e.g. 'Expression', 'Reading', 'Meaning', 'Audio', 'Image') */
  name: string
  /** Semantic type of the field */
  field_type?: "text" | "textarea" | "image" | "audio" | "diagram" | string
  /** Whether the field is required */
  required?: boolean
  /** Descriptive guidance for the field */
  description?: string
  /** Placeholder text */
  placeholder?: string
}

export interface CardFieldsFormProps {
  /** Array of field definitions from the Note Type */
  fieldDefs: CardFieldDef[]
  /** Current field values mapped by field name */
  values: Record<string, string>
  /** Change callback when any field is edited */
  onChange: (values: Record<string, string>) => void
  /** Optional tags associated with the card/note */
  tags?: string[]
  /** Callback when tags list is updated */
  onTagsChange?: (tags: string[]) => void
  /** Media URL resolver for audio / image filenames */
  resolveMediaUrl?: (filenameOrUrl: string) => string | undefined
  /** Async media upload handler when user uploads media for a field */
  onMediaUpload?: (fieldName: string, file: File) => Promise<string | void>
  /** Form submission callback (triggered on button click or Ctrl+Enter) */
  onSubmit?: () => void
  /** Disables all fields and actions (e.g. while submitting) */
  disabled?: boolean
  /** Validation errors map keyed by field name */
  errors?: Record<string, string>
  /** Enables rich Markdown preview toggle on multiline textareas (default: true) */
  enableMarkdownPreview?: boolean
  /** Additional container styling */
  className?: string
}

function isMultilineField(field: CardFieldDef, value: string): boolean {
  if (field.field_type === "textarea") return true
  if (field.field_type === "audio" || field.field_type === "image") return false
  if (value.length > 50 || value.includes("\n")) return true
  const lowerName = field.name.toLowerCase()
  return (
    lowerName.includes("meaning") ||
    lowerName.includes("note") ||
    lowerName.includes("example") ||
    lowerName.includes("sentence") ||
    lowerName.includes("definition") ||
    lowerName.includes("explanation")
  )
}

function isAudioField(field: CardFieldDef): boolean {
  if (field.field_type === "audio") return true
  const lowerName = field.name.toLowerCase()
  return lowerName.includes("audio") || lowerName.includes("sound")
}

function parseAudioUrl(
  rawVal: string,
  resolveMediaUrl?: (path: string) => string | undefined
): string | null {
  if (!rawVal || !rawVal.trim()) return null
  let path = rawVal.trim()
  if (path.startsWith("[sound:") && path.endsWith("]")) {
    path = path.slice(7, -1).trim()
  }
  if (!path) return null
  return resolveMediaUrl ? resolveMediaUrl(path) || path : path
}

export function CardFieldsForm({
  fieldDefs,
  values,
  onChange,
  tags,
  onTagsChange,
  resolveMediaUrl,
  onSubmit,
  disabled = false,
  errors = {},
  enableMarkdownPreview = true,
  className,
}: CardFieldsFormProps) {
  const [previewFields, setPreviewFields] = React.useState<Record<string, boolean>>({})
  const [newTagInput, setNewTagInput] = React.useState("")

  const handleFieldChange = React.useCallback(
    (name: string, val: string) => {
      onChange({
        ...values,
        [name]: val,
      })
    },
    [onChange, values]
  )

  const togglePreview = React.useCallback((fieldName: string) => {
    setPreviewFields((prev) => ({
      ...prev,
      [fieldName]: !prev[fieldName],
    }))
  }, [])

  const handlePlayAudio = React.useCallback(
    (audioUrl: string) => {
      try {
        if (typeof window !== "undefined" && typeof Audio !== "undefined") {
          const audio = new Audio(audioUrl)
          audio.play().catch(() => {
            // Audio autoplay policy or invalid source fallback
          })
        }
      } catch {
        // Fallback for non-browser environments
      }
    },
    []
  )

  const handleKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault()
        if (!disabled) {
          onSubmit?.()
        }
      }
    },
    [disabled, onSubmit]
  )

  const handleAddTag = React.useCallback(() => {
    if (disabled) return
    const trimmed = newTagInput.trim()
    if (!trimmed) return
    const currentTags = tags || []
    if (!currentTags.includes(trimmed)) {
      onTagsChange?.([...currentTags, trimmed])
    }
    setNewTagInput("")
  }, [disabled, newTagInput, tags, onTagsChange])

  const handleRemoveTag = React.useCallback(
    (tagToRemove: string) => {
      if (disabled) return
      const currentTags = tags || []
      onTagsChange?.(currentTags.filter((t) => t !== tagToRemove))
    },
    [disabled, tags, onTagsChange]
  )

  const handleTagInputKeyDown = React.useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault()
        handleAddTag()
      }
    },
    [handleAddTag]
  )

  return (
    <div
      data-slot="card-fields-form"
      onKeyDown={handleKeyDown}
      className={cn("flex flex-col gap-4", className)}
    >
      {fieldDefs.map((field) => {
        const value = values[field.name] ?? ""
        const error = errors[field.name]
        const hasError = Boolean(error)
        const isMultiline = isMultilineField(field, value)
        const isAudio = isAudioField(field)
        const isPreviewing = Boolean(previewFields[field.name])
        const audioUrl = isAudio ? parseAudioUrl(value, resolveMediaUrl) : null

        return (
          <div
            key={field.name}
            data-slot="card-field-group"
            className="flex flex-col gap-1.5"
          >
            {/* Field Header / Label */}
            <div className={cn(cardFieldLabelVariants({ hasError }))}>
              <label
                htmlFor={`field-${field.name}`}
                className="flex items-center gap-1"
              >
                <span>{field.name}</span>
                {field.required && (
                  <span className="text-destructive font-bold" aria-hidden="true">
                    *
                  </span>
                )}
              </label>

              <div className="flex items-center gap-2">
                {/* Audio trigger button */}
                {isAudio && audioUrl && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    disabled={disabled}
                    onClick={() => handlePlayAudio(audioUrl)}
                    aria-label={`Phát âm thanh ${field.name}`}
                    className="h-6 w-6 text-muted-foreground hover:text-primary"
                  >
                    <Volume2 className="size-3.5" />
                  </Button>
                )}

                {/* Markdown preview toggle for multiline text */}
                {isMultiline && enableMarkdownPreview && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-xs"
                    disabled={disabled}
                    onClick={() => togglePreview(field.name)}
                    aria-label={
                      isPreviewing
                        ? `Chỉnh sửa ${field.name}`
                        : `Xem trước ${field.name}`
                    }
                    className="h-6 w-6 text-muted-foreground hover:text-foreground"
                  >
                    {isPreviewing ? (
                      <EyeOff className="size-3.5" />
                    ) : (
                      <Eye className="size-3.5" />
                    )}
                  </Button>
                )}
              </div>
            </div>

            {/* Field Input Widget */}
            {isMultiline ? (
              isPreviewing ? (
                <div
                  data-slot="markdown-preview"
                  className="rounded-lg border border-border/80 bg-card p-3 text-xs sm:text-sm text-foreground leading-relaxed whitespace-pre-wrap min-h-16"
                >
                  {value || (
                    <span className="text-muted-foreground italic">(Trống)</span>
                  )}
                </div>
              ) : (
                <Textarea
                  id={`field-${field.name}`}
                  name={field.name}
                  value={value}
                  required={field.required}
                  placeholder={field.placeholder || `Nhập ${field.name}...`}
                  disabled={disabled}
                  aria-invalid={hasError ? "true" : undefined}
                  aria-describedby={hasError ? `field-${field.name}-error` : undefined}
                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                  className={cn(
                    hasError && "border-destructive focus-visible:ring-destructive"
                  )}
                />
              )
            ) : (
              <Input
                id={`field-${field.name}`}
                name={field.name}
                type="text"
                value={value}
                required={field.required}
                placeholder={field.placeholder || `Nhập ${field.name}...`}
                disabled={disabled}
                aria-invalid={hasError ? "true" : undefined}
                aria-describedby={hasError ? `field-${field.name}-error` : undefined}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                className={cn(
                  hasError && "border-destructive focus-visible:ring-destructive"
                )}
              />
            )}

            {/* Error Message */}
            {hasError && (
              <p
                id={`field-${field.name}-error`}
                role="alert"
                className="text-xs font-medium text-destructive mt-0.5"
              >
                {error}
              </p>
            )}

            {/* Description Guidance */}
            {field.description && !hasError && (
              <p className="text-[11px] text-muted-foreground">
                {field.description}
              </p>
            )}
          </div>
        )
      })}

      {/* Tags Management Section */}
      {(tags !== undefined || onTagsChange !== undefined) && (
        <div data-slot="card-tags-section" className="flex flex-col gap-1.5 pt-2 border-t border-border/60">
          <label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground select-none">
            Thẻ (Tags)
          </label>
          <div className="flex flex-wrap items-center gap-1.5 min-h-8">
            {(tags || []).map((tag) => (
              <Badge
                key={tag}
                variant="secondary"
                className="flex items-center gap-1 px-2 py-0.5 text-xs font-medium"
              >
                <span>{tag}</span>
                {onTagsChange && !disabled && (
                  <button
                    type="button"
                    aria-label={`Xóa tag ${tag}`}
                    onClick={() => handleRemoveTag(tag)}
                    className="ml-0.5 text-muted-foreground hover:text-destructive transition-colors cursor-pointer"
                  >
                    <X className="size-3" />
                  </button>
                )}
              </Badge>
            ))}

            {onTagsChange && (
              <div className="flex items-center gap-1">
                <input
                  type="text"
                  placeholder="Tag mới…"
                  value={newTagInput}
                  disabled={disabled}
                  onChange={(e) => setNewTagInput(e.target.value)}
                  onKeyDown={handleTagInputKeyDown}
                  className="h-7 w-24 sm:w-28 rounded-md border border-input bg-transparent px-2 text-xs outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="icon-xs"
                  disabled={disabled || !newTagInput.trim()}
                  onClick={handleAddTag}
                  aria-label="Thêm tag"
                  className="h-7 w-7"
                >
                  <Plus className="size-3.5" />
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

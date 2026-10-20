import '@/shared/config/i18n'
import type React from 'react'
import { useTranslation } from 'react-i18next'
import { Plus, Tag, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { BROWSE_TAG_MAX_LENGTH } from '../types'

export interface BrowseTagEditorProps {
  tags: string[]
  newTagInput: string
  onNewTagInputChange: (value: string) => void
  onAddTag: () => void
  onRemoveTag: (tag: string) => void
  /** Read-only tags, e.g. on a cloned card where the backend rejects tag edits. */
  disabled?: boolean
  disabledReason?: string
}

/** Enter that only confirms an IME candidate (Japanese, Vietnamese Telex…) must not add a tag. */
function isImeEnter(e: React.KeyboardEvent<HTMLInputElement>) {
  return e.nativeEvent.isComposing || e.keyCode === 229
}

export function BrowseTagEditor({
  tags,
  newTagInput,
  onNewTagInputChange,
  onAddTag,
  onRemoveTag,
  disabled = false,
  disabledReason,
}: BrowseTagEditorProps) {
  const { t } = useTranslation('browse')

  return (
    <div className="space-y-2">
      <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {t('editor.tags_label')}
      </Label>
      <div className="flex gap-1.5">
        <Input
          placeholder={t('editor.new_tag_placeholder')}
          value={newTagInput}
          onChange={(e) => onNewTagInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !isImeEnter(e)) onAddTag()
          }}
          maxLength={BROWSE_TAG_MAX_LENGTH}
          disabled={disabled}
          title={disabled ? disabledReason : undefined}
          className="h-8 rounded-lg text-xs bg-muted/50"
        />
        <Button
          size="sm"
          variant="outline"
          className="h-8 px-2.5 rounded-lg text-xs bg-muted/50 hover:bg-muted border-border"
          onClick={onAddTag}
          disabled={disabled}
          title={disabled ? disabledReason : undefined}
        >
          <Plus className="size-3.5" />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5 pt-1.5">
        {tags.length === 0 ? (
          <span className="text-[11px] text-muted-foreground italic">
            {t('editor.no_tags')}
          </span>
        ) : (
          tags.map((tag) => (
            <Badge
              key={tag}
              variant="secondary"
              className="gap-1 pl-1.5 pr-1 py-0.5 text-[11px] rounded-md font-semibold select-none group"
            >
              <Tag className="size-2.5 opacity-60" />
              <span>{tag}</span>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => onRemoveTag(tag)}
                  className="p-0.5 rounded-full hover:bg-muted-foreground/15 text-muted-foreground hover:text-foreground shrink-0"
                >
                  <X className="size-2.5" />
                </button>
              )}
            </Badge>
          ))
        )}
      </div>
    </div>
  )
}

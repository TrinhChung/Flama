import '@/shared/config/i18n'
import { useTranslation } from 'react-i18next'
import { Plus, Tag, X } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

export type StudyQuickEditTagsProps = {
  tags: string[]
  newTagInput: string
  onNewTagInputChange: (value: string) => void
  onAddTag: () => void
  onRemoveTag: (tag: string) => void
}

export function StudyQuickEditTags({
  tags,
  newTagInput,
  onNewTagInputChange,
  onAddTag,
  onRemoveTag,
}: StudyQuickEditTagsProps) {
  const { t } = useTranslation('study')

  return (
    <div className="space-y-2 pt-2 border-t border-border/50">
      <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        {t('quick_edit.tags_label')}
      </Label>
      <div className="flex gap-1.5">
        <Input
          placeholder={t('quick_edit.add_tag_placeholder')}
          value={newTagInput}
          onChange={(e) => onNewTagInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              onAddTag()
            }
          }}
          className="h-10 sm:h-8 rounded-lg text-base sm:text-xs bg-muted/50 flex-1"
        />
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-10 sm:h-8 px-3.5 sm:px-2.5 rounded-lg text-xs font-semibold bg-muted/50 hover:bg-muted border-border shrink-0"
          onClick={onAddTag}
        >
          <Plus className="size-3.5 mr-1" /> {t('quick_edit.add_tag')}
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5 pt-1">
        {tags.length === 0 ? (
          <span className="text-[11px] text-muted-foreground italic">
            {t('quick_edit.no_tags')}
          </span>
        ) : (
          tags.map((tag) => (
            <Badge
              key={tag}
              variant="secondary"
              className="gap-1 pl-2 sm:pl-1.5 pr-1.5 sm:pr-1 py-1 sm:py-0.5 text-xs sm:text-[11px] rounded-md font-semibold select-none group"
            >
              <Tag className="size-3 sm:size-2.5 opacity-60" />
              <span>{tag}</span>
              <button
                type="button"
                onClick={() => onRemoveTag(tag)}
                className="p-1 sm:p-0.5 rounded-full hover:bg-muted-foreground/15 text-muted-foreground hover:text-foreground shrink-0"
                aria-label={`Remove tag ${tag}`}
              >
                <X className="size-3 sm:size-2.5" />
              </button>
            </Badge>
          ))
        )}
      </div>
    </div>
  )
}

import { Link } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { PublishNoteTypeSelector } from '../PublishNoteTypeSelector'

type SimpleNoteType = {
  id: string
  name: string
  field_count?: number
  publish_status?: string
  is_marketplace_install?: boolean
}

interface PublishNoteTypeStep1BasicProps {
  isEditMode: boolean
  noteTypes: SimpleNoteType[]
  sourceNoteTypeId: string
  selectedNoteType?: SimpleNoteType
  isSelectedInstalledCopy: boolean
  isSelectedAlreadyPublished: boolean
  fieldDefs: any[]
  templates: any[]
  title: string
  previewText: string
  description: string
  tags: string
  changelog: string
  fieldErrors: Record<string, string>
  setSourceNoteTypeId: (id: string) => void
  setTitle: (val: string) => void
  setPreviewText: (val: string) => void
  setDescription: (val: string) => void
  setTags: (val: string) => void
  setChangelog: (val: string) => void
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

export function PublishNoteTypeStep1Basic({
  isEditMode,
  noteTypes,
  sourceNoteTypeId,
  selectedNoteType,
  isSelectedInstalledCopy,
  isSelectedAlreadyPublished,
  fieldDefs,
  templates,
  title,
  previewText,
  description,
  tags,
  changelog,
  fieldErrors,
  setSourceNoteTypeId,
  setTitle,
  setPreviewText,
  setDescription,
  setTags,
  setChangelog,
  clearFieldError,
}: PublishNoteTypeStep1BasicProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      {/* Installed / Already Published Warnings */}
      {isSelectedInstalledCopy && (
        <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{t('publish_notetype.installed_warning', { defaultValue: 'Note Type cài từ Marketplace không thể chia sẻ lại' })}</span>
        </div>
      )}

      {isSelectedAlreadyPublished && (
        <div className="p-3.5 rounded-xl border border-primary/30 bg-primary/10 text-foreground text-xs flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-primary shrink-0" />
            <span>{t('publish_notetype.already_published_warning', { defaultValue: 'NoteType này đã được xuất bản trên Marketplace' })}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button size="sm" variant="outline" asChild className="h-7 text-xs rounded-lg">
              <Link to={`/marketplace/note-types/${sourceNoteTypeId}`}>
                {t('publish_notetype.btn_view_existing', { defaultValue: 'Xem mẫu thẻ trên Marketplace' })}
              </Link>
            </Button>
            <Button size="sm" asChild className="h-7 text-xs rounded-lg">
              <Link to={`/marketplace/note-types/publish?id=${sourceNoteTypeId}&edit=1`}>
                {t('publish_notetype.btn_edit_existing', { defaultValue: 'Chỉnh sửa thông tin' })}
              </Link>
            </Button>
          </div>
        </div>
      )}

      {/* Source Note Type Selector */}
      <div className="space-y-2">
        <Label htmlFor="nt-select" className="text-xs font-semibold flex items-center justify-between">
          <span>
            {t('publish_notetype.select_notetype_label', { defaultValue: 'Chọn NoteType nguồn' })}{' '}
            <span className="text-destructive">*</span>
          </span>
          {selectedNoteType?.field_count !== undefined && (
            <span className="text-[11px] text-muted-foreground font-normal">
              {selectedNoteType.field_count} {t('publish_notetype.fields_unit', { defaultValue: 'trường' })}
            </span>
          )}
        </Label>
        {isEditMode ? (
          <div className="p-3 rounded-xl border border-border/80 bg-muted/40 text-xs font-medium text-foreground">
            {selectedNoteType?.name || title} (ID: {sourceNoteTypeId})
          </div>
        ) : (
          <PublishNoteTypeSelector
            noteTypes={noteTypes}
            selectedNoteTypeId={sourceNoteTypeId}
            onSelectNoteType={(nt) => {
              setSourceNoteTypeId(nt.id)
              clearFieldError('sourceNoteTypeId')
              if (!title) setTitle(nt.name)
            }}
            hasError={Boolean(fieldErrors.sourceNoteTypeId)}
          />
        )}
        <FieldErrorMessage error={fieldErrors.sourceNoteTypeId} />
      </div>

      {/* NoteType Field & Template Badge Summary */}
      {sourceNoteTypeId ? (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-3.5 space-y-2 text-xs">
          <div className="font-bold text-foreground flex items-center justify-between">
            <span>Cấu trúc NoteType đã chọn:</span>
            <span className="text-[11px] text-muted-foreground font-mono">ID: {sourceNoteTypeId}</span>
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            {fieldDefs.length > 0 ? (
              fieldDefs.map((f, i) => (
                <Badge key={i} variant="secondary" className="text-[11px] bg-background border font-semibold">
                  Trường: {f.name}
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">Không có trường tùy biến</span>
            )}
            {templates.length > 0 ? (
              templates.map((tItem, i) => (
                <Badge key={i} variant="outline" className="text-[11px] bg-background border-primary/30 text-primary font-semibold">
                  Thẻ: {tItem.name}
                </Badge>
              ))
            ) : (
              <span className="text-muted-foreground">Không có mẫu mặt thẻ</span>
            )}
          </div>
        </div>
      ) : null}

      {/* Title */}
      <div className="space-y-2">
        <Label htmlFor="nt-title" className="text-xs font-semibold flex items-center justify-between">
          <span>{t('publish_deck.step1.title_label', { defaultValue: 'Tiêu đề hiển thị (Listing Title)' })} <span className="text-destructive">*</span></span>
        </Label>
        <Input
          id="nt-title"
          placeholder="Ví dụ: Mẫu thẻ Kanji đa tầng có Furigana & Audio, Thẻ Code Syntax Highlight..."
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            clearFieldError('title')
          }}
          className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
            fieldErrors.title ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
          }`}
        />
        <FieldErrorMessage error={fieldErrors.title} />
      </div>

      {/* Short Preview */}
      <div className="space-y-2">
        <Label htmlFor="nt-preview" className="text-xs font-semibold flex items-center justify-between">
          <span>{t('publish_deck.step1.preview_label', { defaultValue: 'Xem trước ngắn (Preview Text)' })} <span className="text-destructive">*</span></span>
        </Label>
        <Input
          id="nt-preview"
          placeholder="1 dòng tóm tắt thiết kế mẫu thẻ để người học xem nhanh trên danh sách"
          value={previewText}
          onChange={(e) => {
            setPreviewText(e.target.value)
            clearFieldError('previewText')
          }}
          className={`h-10 text-xs sm:text-sm rounded-xl ${
            fieldErrors.previewText ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
          }`}
          maxLength={160}
        />
        <div className="flex items-center justify-between text-[11px] text-muted-foreground">
          <div><FieldErrorMessage error={fieldErrors.previewText} /></div>
          <div>{previewText.length}/160 ký tự</div>
        </div>
      </div>

      {/* Description */}
      <div className="space-y-2">
        <Label htmlFor="nt-desc" className="text-xs font-semibold flex items-center justify-between">
          <span>{t('publish_deck.step1.desc_label', { defaultValue: 'Mô tả chi tiết mẫu thẻ' })} <span className="text-destructive">*</span></span>
        </Label>
        <Textarea
          id="nt-desc"
          rows={5}
          placeholder="Mô tả chi tiết cấu trúc field, thiết kế CSS, cách trình bày và trường hợp sử dụng phù hợp…"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value)
            clearFieldError('description')
          }}
          className={`text-xs sm:text-sm rounded-xl leading-relaxed ${
            fieldErrors.description ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
          }`}
        />
        <FieldErrorMessage error={fieldErrors.description} />
      </div>

      {/* Tags & Changelog in 2 columns */}
      <div className="grid gap-4 sm:grid-cols-2 pt-2 border-t border-border/40">
        <div className="space-y-1.5">
          <Label htmlFor="nt-tags" className="text-xs font-semibold">{t('publish_deck.step1.tags_label', { defaultValue: 'Thẻ Tags (cách nhau dấu phẩy)' })}</Label>
          <Input
            id="nt-tags"
            placeholder="cloze, kanji, code..."
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="nt-changelog" className="text-xs font-semibold">{t('publish_deck.step1.changelog_label', { defaultValue: 'Ghi chú phát hành (Changelog)' })}</Label>
          <Input
            id="nt-changelog"
            placeholder="Ví dụ: Hỗ trợ syntax highlight và audio tự động..."
            value={changelog}
            onChange={(e) => setChangelog(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl"
          />
        </div>
      </div>
    </div>
  )
}

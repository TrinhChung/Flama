import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { PublishDeckTree } from '../PublishDeckTree'
import { type PublishDeckOption } from '../../publishApi'
import { FieldErrorMessage } from './PublishWizardTypes'

interface PublishStep1BasicInfoProps {
  isEditMode: boolean
  decks: PublishDeckOption[]
  sourceDeckId: string
  deckItem: any
  title: string
  isTitleManuallyEdited: boolean
  previewText: string
  description: string
  tags: string
  changelog: string
  isReleaseVersioned: boolean
  fieldErrors: Record<string, string>
  setSourceDeckId: (id: string) => void
  setTitle: (title: string) => void
  setIsTitleManuallyEdited: (val: boolean) => void
  setPreviewText: (preview: string) => void
  setDescription: (desc: string) => void
  setTags: (tags: string) => void
  setChangelog: (changelog: string) => void
  clearFieldError: (name: string) => void
}

export function PublishStep1BasicInfo({
  isEditMode,
  decks,
  sourceDeckId,
  deckItem,
  title,
  isTitleManuallyEdited,
  previewText,
  description,
  tags,
  changelog,
  isReleaseVersioned,
  fieldErrors,
  setSourceDeckId,
  setTitle,
  setIsTitleManuallyEdited,
  setPreviewText,
  setDescription,
  setTags,
  setChangelog,
  clearFieldError,
}: PublishStep1BasicInfoProps) {
  return (
    <div className="space-y-5 animate-in fade-in duration-200">
      <div className="space-y-2">
        <Label className="text-xs font-semibold flex items-center justify-between">
          <span>Bộ thẻ nguồn chia sẻ <span className="text-destructive">*</span></span>
        </Label>
        {isEditMode ? (
          <div className="p-3.5 rounded-xl border border-border/80 bg-muted/30 text-xs font-semibold text-foreground flex items-center justify-between">
            <span>
              {decks.find((d) => String(d.id) === String(sourceDeckId || deckItem?.source_deck_id))?.name ||
                deckItem?.title ||
                title ||
                'Bộ thẻ nguồn'}
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">
              ID: {sourceDeckId || deckItem?.source_deck_id}
            </span>
          </div>
        ) : (
          <PublishDeckTree
            decks={decks}
            selectedDeckId={sourceDeckId}
            onSelectDeck={(deck: PublishDeckOption) => {
              setSourceDeckId(String(deck.id))
              clearFieldError('sourceDeckId')
              if (!isTitleManuallyEdited) {
                setTitle(deck.name)
              }
            }}
          />
        )}
        <FieldErrorMessage error={fieldErrors.sourceDeckId} />
      </div>

      {/* Title */}
      <div className="space-y-2">
        <Label htmlFor="title" className="text-xs font-semibold flex items-center justify-between">
          <span>Tiêu đề hiển thị trên Marketplace <span className="text-destructive">*</span></span>
        </Label>
        <Input
          id="title"
          placeholder="Ví dụ: 2000 Từ vựng JLPT N3 Đọc - Hiểu Thực chiến, Flashcard Tiếng Anh Y Khoa..."
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            setIsTitleManuallyEdited(true)
            clearFieldError('title')
          }}
          className={`h-10 text-xs sm:text-sm rounded-xl font-medium ${
            fieldErrors.title ? 'border-destructive focus-visible:ring-destructive bg-destructive/5' : ''
          }`}
        />
        <FieldErrorMessage error={fieldErrors.title} />
      </div>

      {/* Preview Text */}
      <div className="space-y-2">
        <Label htmlFor="preview_text" className="text-xs font-semibold flex items-center justify-between">
          <span>Tóm tắt xem trước ngắn (Preview Text) <span className="text-destructive">*</span></span>
        </Label>
        <Input
          id="preview_text"
          placeholder="1-2 câu tóm tắt nội dung hấp dẫn để người học nắm bắt nhanh khi lướt danh sách"
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
        <Label htmlFor="description" className="text-xs font-semibold flex items-center justify-between">
          <span>Mô tả chi tiết bộ thẻ <span className="text-destructive">*</span></span>
        </Label>
        <Textarea
          id="description"
          rows={5}
          placeholder="Giới thiệu chi tiết lộ trình, phương pháp ghi nhớ, các trường dữ liệu và điểm đặc sắc của bộ flashcard…"
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
          <Label htmlFor="tags" className="text-xs font-semibold">Thẻ Tags (cách nhau dấu phẩy)</Label>
          <Input
            id="tags"
            placeholder="n3, tu-vung, y-khoa, audio"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            className="h-10 text-xs sm:text-sm rounded-xl"
          />
        </div>
        {isReleaseVersioned ? (
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs">
            <p className="font-semibold text-foreground">Changelog được quản lý theo release</p>
            <p className="mt-1 leading-relaxed text-muted-foreground">
              Lưu cấu hình listing tại đây; ghi chú nội dung thay đổi khi tạo phiên bản mới.
            </p>
          </div>
        ) : (
          <div className="space-y-1.5">
            <Label htmlFor="changelog" className="text-xs font-semibold">Ghi chú phát hành (Changelog)</Label>
            <Input
              id="changelog"
              placeholder="Ví dụ: Bổ sung 50 ví dụ thực tế và audio tự nhiên..."
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
              className="h-10 text-xs sm:text-sm rounded-xl"
            />
          </div>
        )}
      </div>
    </div>
  )
}

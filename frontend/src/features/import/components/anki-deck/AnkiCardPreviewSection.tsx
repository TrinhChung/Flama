import { Button } from '@/components/ui/button'
import { NativeSelect } from '@/components/ui/native-select'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'

interface AnkiCardPreviewSectionProps {
  showPreviewSection: boolean
  setShowPreviewSection: (val: boolean) => void
  activePreviewNote: any
  previewNotes: any[]
  previewNoteIndex: number
  setPreviewNoteIndex: (val: number) => void
  previewSide: 'front' | 'back'
  setPreviewSide: (val: 'front' | 'back') => void
  previewTemplates: any[]
  previewTemplateId: string
  setPreviewTemplateId: (val: string) => void
  previewResult: any
  selectedFlamaModelId: string
  previewNoteType: any
  isLoadingPreview: boolean
  previewError: string | null
}

export function AnkiCardPreviewSection({
  showPreviewSection,
  setShowPreviewSection,
  activePreviewNote,
  previewNotes,
  previewNoteIndex,
  setPreviewNoteIndex,
  previewSide,
  setPreviewSide,
  previewTemplates,
  previewTemplateId,
  setPreviewTemplateId,
  previewResult,
  selectedFlamaModelId,
  previewNoteType,
  isLoadingPreview,
  previewError,
}: AnkiCardPreviewSectionProps) {
  if (!showPreviewSection) return null

  return (
    <div className="space-y-2 mb-4">
      <div className="flex items-center justify-between text-xs font-bold border-b pb-1.5">
        <div className="flex items-center gap-2">
          <span>Thẻ Anki #{activePreviewNote?.noteId || '—'}</span>
          {previewNotes.length > 1 && (
            <NativeSelect
              value={String(previewNoteIndex)}
              onChange={(event) => setPreviewNoteIndex(Number(event.target.value))}
              className="h-7 w-28 text-[11px]"
            >
              {previewNotes.map((note, index) => (
                <option key={note.noteId} value={index}>Mẫu {index + 1}</option>
              ))}
            </NativeSelect>
          )}
        </div>
        <Button size="xs" variant="ghost" onClick={() => setShowPreviewSection(false)} className="h-6 text-[11px]">
          Ẩn
        </Button>
      </div>
      <NoteTypeLivePreview
        cardId={`anki-deck-preview-${activePreviewNote?.noteId || 'empty'}`}
        side={previewSide}
        onSideChange={setPreviewSide}
        templates={previewTemplates.map((template) => ({ id: template.id, name: template.name }))}
        selectedTemplateId={previewTemplateId}
        onSelectTemplate={setPreviewTemplateId}
        frontPayload={previewResult?.front_renderer_payload}
        backPayload={previewResult?.back_renderer_payload}
        frontHtml={previewResult?.front_html}
        backHtml={previewResult?.back_html}
        scope="anki_deck_import_preview"
        scopeId={selectedFlamaModelId}
        fieldDefs={previewNoteType?.field_defs || []}
        isLoading={isLoadingPreview}
        error={previewError || (previewNotes.length === 0 ? 'Deck không có thẻ thuộc NoteType Anki đã chọn.' : null)}
        title="Card Review Preview"
        subtitle="Dữ liệu thật sau khi áp dụng ánh xạ trường"
        containerHeightClass="h-[clamp(18rem,48vh,34rem)] min-h-[288px]"
      />
    </div>
  )
}

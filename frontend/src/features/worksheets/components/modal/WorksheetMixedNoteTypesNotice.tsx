import { AlertTriangle, FolderTree } from 'lucide-react'
import { Button } from '@/components/ui/button'

/** Mapping-step blocker for decks that mix several note types. */
export function WorksheetMixedNoteTypesNotice({
  noteTypeCount,
  onChooseAnotherDeck,
}: {
  noteTypeCount: number
  onChooseAnotherDeck: () => void
}) {
  return (
    <div className="p-6 flex flex-col items-center justify-center text-center space-y-4 max-w-lg mx-auto h-full">
      <div className="size-12 rounded-full bg-amber-500/10 text-amber-600 flex items-center justify-center">
        <AlertTriangle className="size-6" />
      </div>
      <div className="space-y-1">
        <h3 className="text-base font-bold text-foreground">
          Bộ thẻ chứa {noteTypeCount} loại thẻ khác nhau
        </h3>
        <p className="text-xs text-muted-foreground leading-relaxed">
          Để hệ thống trích xuất dữ liệu và in bài tập chính xác nhất, vui lòng chọn một bộ thẻ chỉ chứa <strong>1 loại thẻ duy nhất</strong>.
        </p>
      </div>
      <Button onClick={onChooseAnotherDeck} size="sm" className="gap-1.5 font-bold">
        <FolderTree className="size-3.5" />
        <span>Chọn bộ thẻ khác</span>
      </Button>
    </div>
  )
}

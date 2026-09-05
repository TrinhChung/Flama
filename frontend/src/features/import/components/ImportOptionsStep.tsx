import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { DeckSelectionTreeView } from '../components/DeckSelectionTreeView'
import { Check, Layers } from 'lucide-react'
import type { useFileImportWizard } from '../hooks/useFileImportWizard'

interface ImportOptionsStepProps {
  wizard: ReturnType<typeof useFileImportWizard>
}

export function ImportOptionsStep({ wizard }: ImportOptionsStepProps) {
  const {
    deckOptions,
    selectedDeckId,
    handleDeckChange,
    noteTypeSelectId,
    autoSelectBadge,
    selectedNoteTypeId,
    setSelectedNoteTypeId,
    noteTypeOptions,
    warnOnNonEmptyDeck,
    handleWarnOnNonEmptyDeckChange,
  } = wizard

  return (
    <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
      <CardHeader className="pb-3 border-b bg-card/50">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Layers className="size-4 text-foreground/80" />
          Cấu hình Deck &amp; Loại Note
        </CardTitle>
        <CardDescription className="text-xs">
          Xác định Deck lưu trữ thẻ và cấu trúc NoteType phù hợp với file import.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <Label className="font-semibold text-xs">Deck đích</Label>
            <DeckSelectionTreeView
              deckOptions={deckOptions}
              selectedDeckId={selectedDeckId}
              onSelectDeck={handleDeckChange}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor={noteTypeSelectId} className="font-semibold text-xs">
                Loại note
              </Label>
              {autoSelectBadge && (
                <Badge variant="outline" className="bg-muted text-muted-foreground border-border/80 text-[11px] font-medium gap-1">
                  <Check className="size-3" /> Tự động khớp theo deck
                </Badge>
              )}
            </div>
            <NativeSelect
              id={noteTypeSelectId}
              value={selectedNoteTypeId}
              onChange={(e) => {
                setSelectedNoteTypeId(e.target.value)
              }}
            >
              {noteTypeOptions.map((nt) => (
                <option key={nt.id} value={nt.id}>
                  {nt.name}
                </option>
              ))}
            </NativeSelect>
          </div>
        </div>

        <div className="flex items-start space-x-2 mt-4 pt-4 border-t border-border/40">
          <Checkbox
            id="warnOnNonEmptyDeckCheckbox"
            checked={warnOnNonEmptyDeck}
            onCheckedChange={(checked) => handleWarnOnNonEmptyDeckChange(Boolean(checked))}
          />
          <div className="grid gap-1.5 leading-none">
            <Label htmlFor="warnOnNonEmptyDeckCheckbox" className="text-xs font-semibold cursor-pointer">
              Cảnh báo khi nhập vào Deck đã có dữ liệu (Khuyên dùng)
            </Label>
            <p className="text-[11px] text-muted-foreground">
              Nếu deck đích hiện đang có sẵn thẻ, hệ thống sẽ nhắc nhở bạn xác nhận trước khi thực hiện để tránh ghi đè nhầm dữ liệu cũ.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

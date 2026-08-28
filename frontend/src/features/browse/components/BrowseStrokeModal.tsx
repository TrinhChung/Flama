import { useState, useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import {
  AlertCircle,
  Check,
  Eye,
  Languages,
  LoaderCircle,
  PenTool,
} from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi, type GenerateStrokesResponse } from '@/app/api'
import type { useBrowseState } from '../hooks/useBrowseState'

interface BrowseStrokeModalProps {
  browse: ReturnType<typeof useBrowseState>
  isOpen: boolean
  onClose: () => void
  mode?: 'single' | 'batch'
  cardId?: string | null
}

export function BrowseStrokeModal({
  browse,
  isOpen,
  onClose,
  mode = 'batch',
  cardId,
}: BrowseStrokeModalProps) {
  const {
    selectedCards,
    selectedDeckId,
    cardDetailQuery,
    editFieldValues,
    setEditFieldValues,
    queryClient,
  } = browse

  // Available field names
  const detailFields = cardDetailQuery.data?.fields || []
  const availableFieldNames = detailFields.map((f) => f.name)
  const defaultSource =
    availableFieldNames.find((f) =>
      ['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'term', 'front'].includes(
        f.toLowerCase(),
      ),
    ) ||
    availableFieldNames[0] ||
    'Expression'

  const defaultTarget =
    availableFieldNames.find((f) =>
      ['strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes'].includes(
        f.toLowerCase(),
      ),
    ) || 'StrokeDiagram'

  const [sourceField, setSourceField] = useState(defaultSource)
  const [targetField, setTargetField] = useState(defaultTarget)
  const [locale, setLocale] = useState('ja')
  const [outputFormat, setOutputFormat] = useState<'html' | 'urls'>('html')
  const [overwrite, setOverwrite] = useState(false)
  const [maxChars] = useState(15)

  // Single card preview / sample text
  const currentCardValue = editFieldValues[sourceField] || ''
  const [sampleText, setSampleText] = useState(
    mode === 'single' && currentCardValue ? currentCardValue : '日本語を勉強する (学习中文)',
  )

  useEffect(() => {
    if (mode === 'single' && editFieldValues[sourceField]) {
      setSampleText(editFieldValues[sourceField])
    }
  }, [mode, sourceField, editFieldValues])

  // Stroke preview query
  const previewQuery = useQuery<GenerateStrokesResponse>({
    queryKey: ['stroke-preview', sampleText, locale, outputFormat, maxChars],
    queryFn: () =>
      appApi.generateStrokes({
        text: sampleText,
        locale,
        format: outputFormat,
        max_characters: maxChars,
      }),
    enabled: isOpen && Boolean(sampleText.trim()),
    staleTime: 1000 * 60 * 5,
  })

  // Batch generate mutation
  const batchMutation = useMutation({
    mutationFn: () => {
      const targetCardIds = mode === 'single' && cardId ? [cardId] : selectedCards
      return appApi.batchGenerateStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        card_ids: targetCardIds.length ? targetCardIds : undefined,
        format: outputFormat,
        overwrite,
        max_characters: maxChars,
      })
    },
    onSuccess: (res) => {
      toast.success(
        `Đã tạo sơ đồ nét thành công! Cập nhật: ${res.updated}, Bỏ qua: ${res.skipped} / Tổng: ${res.total_processed} thẻ.`,
      )
      void queryClient.invalidateQueries({ queryKey: ['browse-cards'] })
      void queryClient.invalidateQueries({ queryKey: ['card-detail'] })
      onClose()
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Có lỗi xảy ra khi tạo sơ đồ nét.')
    },
  })

  const handleApplySingle = () => {
    if (previewQuery.data?.output) {
      setEditFieldValues((prev) => ({
        ...prev,
        [targetField]: previewQuery.data?.output || '',
      }))
      toast.success(`Đã điền sơ đồ nét vào trường "${targetField}". Bấm "Lưu thẻ" để hoàn tất!`)
      onClose()
    } else {
      toast.warning('Không tìm thấy ký tự Kanji/Hanzi nào trong văn bản nguồn.')
    }
  }

  const targetCount =
    mode === 'single'
      ? 1
      : selectedCards.length > 0
        ? selectedCards.length
        : 'Tất cả thẻ trong Deck'

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[90vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <PenTool className="size-4.5 shrink-0" />
            </div>
            <span>Tạo sơ đồ thứ tự nét Kanji & Hanzi</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            Tự động trích xuất chữ Hán và nhúng sơ đồ nét SVG tĩnh (KanjiVG / MakeMeAHanzi) vào thẻ học.
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {/* Target summary badge */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/60">
            <span className="text-muted-foreground">Phạm vi áp dụng:</span>
            <Badge variant="secondary" className="font-bold text-xs">
              {typeof targetCount === 'number' ? `${targetCount} thẻ` : targetCount}
            </Badge>
          </div>

          {/* Form grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Source field */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Trường nguồn (Source Field)
              </Label>
              {availableFieldNames.length > 0 ? (
                <NativeSelect
                  value={sourceField}
                  onChange={(e) => setSourceField(e.target.value)}
                  className="h-9 text-xs rounded-lg bg-background"
                >
                  {availableFieldNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </NativeSelect>
              ) : (
                <Input
                  value={sourceField}
                  onChange={(e) => setSourceField(e.target.value)}
                  placeholder="ví dụ: Expression, Word..."
                  className="h-9 text-xs bg-background"
                />
              )}
            </div>

            {/* Target field */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Trường lưu (Target Field)
              </Label>
              <Input
                value={targetField}
                onChange={(e) => setTargetField(e.target.value)}
                placeholder="ví dụ: StrokeDiagram, KanjiStrokes..."
                className="h-9 text-xs bg-background"
              />
            </div>

            {/* Locale */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Languages className="size-3.5" />
                <span>Ngôn ngữ / Quy tắc nét</span>
              </Label>
              <NativeSelect
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                className="h-9 text-xs rounded-lg bg-background"
              >
                <option value="ja">Tiếng Nhật (Kanji - KanjiVG)</option>
                <option value="zh-CN">Tiếng Trung (Giản thể - zh-CN)</option>
                <option value="zh-TW">Tiếng Trung (Phồn thể - zh-TW)</option>
              </NativeSelect>
            </div>

            {/* Output format */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Định dạng lưu trữ
              </Label>
              <NativeSelect
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as 'html' | 'urls')}
                className="h-9 text-xs rounded-lg bg-background"
              >
                <option value="html">HTML Embed (&lt;img&gt; sẵn sàng render)</option>
                <option value="urls">Danh sách URL JSON</option>
              </NativeSelect>
            </div>
          </div>

          {/* Overwrite option */}
          <div className="flex items-center space-x-2 pt-1">
            <Checkbox
              id="overwrite-strokes"
              checked={overwrite}
              onCheckedChange={(c) => setOverwrite(Boolean(c))}
            />
            <Label
              htmlFor="overwrite-strokes"
              className="text-xs font-medium cursor-pointer select-none text-foreground"
            >
              Ghi đè nếu trường đích đã có dữ liệu
            </Label>
          </div>

          {/* Live Preview Area */}
          <div className="space-y-2 pt-2 border-t border-border/60">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Eye className="size-3.5 text-primary" />
                <span>Xem trước kết quả trích xuất</span>
              </span>
              {previewQuery.isFetching && (
                <span className="text-[11px] text-primary flex items-center gap-1 font-medium">
                  <LoaderCircle className="size-3 animate-spin" /> Đang tải…
                </span>
              )}
            </div>

            <div className="space-y-1.5">
              <Input
                value={sampleText}
                onChange={(e) => setSampleText(e.target.value)}
                placeholder="Nhập văn bản thử nghiệm..."
                className="h-8 text-xs bg-muted/40"
              />
            </div>

            {/* Extracted characters badges */}
            {previewQuery.data?.characters && previewQuery.data.characters.length > 0 && (
              <div className="flex flex-wrap items-center gap-1 pt-1">
                <span className="text-[11px] text-muted-foreground mr-1">Chữ Hán tìm thấy:</span>
                {previewQuery.data.characters.map((c) => (
                  <Badge key={c} variant="secondary" className="text-xs font-bold px-1.5 py-0.5">
                    {c}
                  </Badge>
                ))}
              </div>
            )}

            {/* Rendered SVG Preview */}
            <div className="p-3.5 rounded-xl bg-card border border-border/80 min-h-24 flex items-center justify-center">
              {previewQuery.data?.items && previewQuery.data.items.length > 0 ? (
                <div className="flex flex-wrap gap-2.5 justify-center items-center">
                  {previewQuery.data.items.map((item) => (
                    <div
                      key={item.hex}
                      className="group relative flex flex-col items-center bg-background border border-border/60 rounded-xl p-1.5 shadow-xs hover:border-primary/50 transition-all"
                    >
                      <img
                        src={item.url}
                        alt={item.char}
                        title={item.char}
                        className="w-16 h-16 sm:w-20 sm:h-20 object-contain rounded-lg"
                      />
                      <span className="text-[10px] font-bold text-muted-foreground mt-1">
                        {item.char}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground text-xs py-2">
                  <AlertCircle className="size-5 mx-auto mb-1 opacity-50" />
                  <span>Không tìm thấy chữ Hán nào để hiển thị thứ tự nét.</span>
                </div>
              )}
            </div>
          </div>
        </div>

        <DialogFooter className="px-5 py-3 border-t bg-muted/20 flex flex-row items-center justify-end gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onClose} className="h-9 text-xs rounded-xl">
            Hủy
          </Button>

          {mode === 'single' ? (
            <Button
              size="sm"
              onClick={handleApplySingle}
              disabled={!previewQuery.data?.items?.length}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              <Check className="size-3.5" />
              <span>Áp dụng vào thẻ</span>
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => batchMutation.mutate()}
              disabled={batchMutation.isPending}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              {batchMutation.isPending ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <PenTool className="size-3.5" />
              )}
              <span>Tạo hàng loạt ({typeof targetCount === 'number' ? targetCount : 'Deck'})</span>
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

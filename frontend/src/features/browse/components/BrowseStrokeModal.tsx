import { useState, useEffect, useMemo } from 'react'
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
  Code,
  Copy,
  Eye,
  Info,
  Languages,
  Layers,
  LoaderCircle,
  PenTool,
  Sparkles,
} from 'lucide-react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi, type GenerateStrokesResponse } from '@/app/api'
import { resolveBackendUrl } from '@/config/env'
import type { useBrowseState, CardDetailResponse } from '../hooks/useBrowseState'

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
    activeCardId,
    cards,
    decksQuery,
    cardDetailQuery,
    editFieldValues,
    setEditFieldValues,
    queryClient,
  } = browse

  // Determine target card ID to resolve actual Note Type fields
  const targetCardId =
    cardId || activeCardId || (selectedCards.length > 0 ? selectedCards[0] : cards[0]?.card_id)

  // Fetch card detail for target card if not already active in cardDetailQuery
  const targetCardQuery = useQuery({
    queryKey: ['browse', 'stroke-modal-card-detail', targetCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${targetCardId}`),
    enabled: isOpen && Boolean(targetCardId) && cardDetailQuery.data?.card?.card_id !== targetCardId,
    staleTime: 1000 * 60 * 5,
  })

  // Extract actual fields of the Note Type currently in use
  const actualNoteFields = useMemo(() => {
    if (cardDetailQuery.data?.card?.card_id === targetCardId && cardDetailQuery.data?.fields?.length) {
      return cardDetailQuery.data.fields
    }
    if (targetCardQuery.data?.fields?.length) {
      return targetCardQuery.data.fields
    }
    if (cardDetailQuery.data?.fields?.length) {
      return cardDetailQuery.data.fields
    }
    return []
  }, [cardDetailQuery.data, targetCardQuery.data, targetCardId])

  const noteFieldNames = useMemo(() => {
    const names = actualNoteFields.map((f) => f.name).filter(Boolean)
    if (names.length > 0) return names
    return ['Expression', 'Reading', 'Meaning', 'StrokeDiagram']
  }, [actualNoteFields])

  // Smart defaults based strictly on actual note fields
  const defaultSource = useMemo(() => {
    return (
      noteFieldNames.find((f) =>
        ['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'term', 'front'].includes(
          f.toLowerCase(),
        ),
      ) ||
      noteFieldNames[0] ||
      'Expression'
    )
  }, [noteFieldNames])

  const defaultTarget = useMemo(() => {
    return (
      noteFieldNames.find((f) =>
        ['strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes', 'stroke'].includes(
          f.toLowerCase(),
        ),
      ) ||
      (noteFieldNames.includes('StrokeDiagram')
        ? 'StrokeDiagram'
        : noteFieldNames[noteFieldNames.length - 1]) ||
      'StrokeDiagram'
    )
  }, [noteFieldNames])

  const [sourceField, setSourceField] = useState(defaultSource)
  const [targetField, setTargetField] = useState(defaultTarget)
  const [isCustomTarget, setIsCustomTarget] = useState(false)
  const [customTargetName, setCustomTargetName] = useState('')

  // Sync state when defaults change
  useEffect(() => {
    if (defaultSource && !noteFieldNames.includes(sourceField)) {
      setSourceField(defaultSource)
    }
    if (defaultTarget && !noteFieldNames.includes(targetField) && !isCustomTarget) {
      setTargetField(defaultTarget)
    }
  }, [defaultSource, defaultTarget, noteFieldNames, isCustomTarget])

  // Resolve actual text content from the selected sourceField across active/target card data
  const resolvedSourceValue = useMemo(() => {
    // 1. From active sidebar edits
    if (editFieldValues[sourceField] !== undefined && editFieldValues[sourceField] !== null && String(editFieldValues[sourceField]).trim()) {
      return String(editFieldValues[sourceField]).trim()
    }
    // 2. From active card note field_values
    if (cardDetailQuery.data?.note?.field_values?.[sourceField] !== undefined && String(cardDetailQuery.data.note.field_values[sourceField]).trim()) {
      return String(cardDetailQuery.data.note.field_values[sourceField]).trim()
    }
    // 3. From target card query note field_values
    if (targetCardQuery.data?.note?.field_values?.[sourceField] !== undefined && String(targetCardQuery.data.note.field_values[sourceField]).trim()) {
      return String(targetCardQuery.data.note.field_values[sourceField]).trim()
    }
    // 4. Fallback from card row
    const matchingCard = cards.find((c) => c.card_id === targetCardId) || cards[0]
    if (matchingCard) {
      const lower = sourceField.toLowerCase()
      if (['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'front'].includes(lower) && matchingCard.word) {
        return matchingCard.word.trim()
      }
      if (['reading', 'kana', 'pinyin'].includes(lower) && matchingCard.reading) {
        return matchingCard.reading.trim()
      }
      if (['meaning', 'vietnamese', 'definition', 'back'].includes(lower) && matchingCard.meaning) {
        return matchingCard.meaning.trim()
      }
    }
    return ''
  }, [
    sourceField,
    editFieldValues,
    cardDetailQuery.data,
    targetCardQuery.data,
    cards,
    targetCardId,
  ])

  // Auto-detect initial locale based on deck name or character composition
  const detectedLocale = useMemo(() => {
    const deckName = (
      decksQuery?.data?.decks?.find((d) => d.id === selectedDeckId)?.name ||
      cardDetailQuery.data?.note?.deck_name ||
      cards.find((c) => c.card_id === targetCardId)?.deck_name ||
      ''
    ).toLowerCase()
    if (/hsk|trung|chinese|hán|zh/i.test(deckName)) {
      return 'zh-CN'
    }
    if (/kanji|n[1-5]|nhật|japanese|ja/i.test(deckName)) {
      return 'ja'
    }
    if (/[汉语话书买卖时间门关开钱鸡车电习爱国难易简单红蓝绿颜]/i.test(resolvedSourceValue)) {
      return 'zh-CN'
    }
    if (/[漢語話書買賣門關開錢雞車電習愛國]/i.test(resolvedSourceValue)) {
      return 'zh-TW'
    }
    return 'ja'
  }, [decksQuery?.data?.decks, cardDetailQuery.data, cards, selectedDeckId, targetCardId, resolvedSourceValue])

  const [locale, setLocale] = useState('ja')

  useEffect(() => {
    if (detectedLocale) {
      setLocale(detectedLocale)
    }
  }, [detectedLocale])

  const [outputFormat, setOutputFormat] = useState<'html' | 'raw' | 'urls'>('html')
  const [overwrite, setOverwrite] = useState(false)
  const [maxChars] = useState(15)
  const [copiedCode, setCopiedCode] = useState(false)

  const [sampleText, setSampleText] = useState(resolvedSourceValue)

  // Automatically update sampleText whenever sourceField, target card, or card data changes
  useEffect(() => {
    setSampleText(resolvedSourceValue)
  }, [resolvedSourceValue, sourceField])

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

  // Resolved effective target field name
  const effectiveTargetField = isCustomTarget ? customTargetName.trim() : targetField

  // Batch generate mutation
  const batchMutation = useMutation({
    mutationFn: () => {
      const targetCardIds = mode === 'single' && cardId ? [cardId] : selectedCards
      if (!sourceField.trim()) {
        throw new Error('Vui lòng chọn hoặc nhập trường nguồn.')
      }
      if (!effectiveTargetField) {
        throw new Error('Vui lòng chọn hoặc nhập trường lưu kết quả.')
      }

      return appApi.batchGenerateStrokes({
        source_field: sourceField,
        target_field: effectiveTargetField,
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
    if (!effectiveTargetField) {
      toast.error('Vui lòng chọn hoặc nhập trường lưu kết quả.')
      return
    }
    if (previewQuery.data?.output) {
      setEditFieldValues((prev) => ({
        ...prev,
        [effectiveTargetField]: previewQuery.data?.output || '',
      }))
      toast.success(`Đã điền sơ đồ nét vào trường "${effectiveTargetField}". Bấm "Lưu thẻ" để hoàn tất!`)
      onClose()
    } else {
      toast.warning('Không tìm thấy ký tự Kanji/Hanzi nào trong văn bản nguồn.')
    }
  }

  const handleCopyCode = async () => {
    if (!previewQuery.data?.output) return
    try {
      await navigator.clipboard.writeText(previewQuery.data.output)
      setCopiedCode(true)
      toast.success('Đã sao chép nội dung xuất vào bộ nhớ tạm!')
      setTimeout(() => setCopiedCode(false), 2000)
    } catch {
      toast.error('Không thể sao chép.')
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
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <PenTool className="size-4.5 shrink-0" />
            </div>
            <span>Tạo sơ đồ thứ tự nét Kanji & Hanzi</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            Tự động trích xuất chữ Hán từ trường nguồn và sinh sơ đồ nét SVG vector tĩnh chuẩn hóa (KanjiVG / MakeMeAHanzi).
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {/* Target summary badge */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/60">
            <span className="text-muted-foreground flex items-center gap-1.5">
              <Layers className="size-3.5 text-primary" />
              <span>Phạm vi áp dụng:</span>
            </span>
            <Badge variant="secondary" className="font-bold text-xs">
              {typeof targetCount === 'number' ? `${targetCount} thẻ` : targetCount}
            </Badge>
          </div>

          {/* Form grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Source field */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                Trường nguồn (Ký tự nguồn)
              </Label>
              <NativeSelect
                value={sourceField}
                onChange={(e) => setSourceField(e.target.value)}
                className="h-9 text-xs rounded-lg bg-background"
              >
                {noteFieldNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </NativeSelect>
            </div>

            {/* Target field */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  Trường lưu (Target Field)
                </Label>
                {isCustomTarget && (
                  <button
                    type="button"
                    onClick={() => setIsCustomTarget(false)}
                    className="text-[11px] text-primary hover:underline"
                  >
                    Chọn từ Note Type
                  </button>
                )}
              </div>

              {!isCustomTarget ? (
                <NativeSelect
                  value={targetField}
                  onChange={(e) => {
                    if (e.target.value === '__custom__') {
                      setIsCustomTarget(true)
                      setCustomTargetName('')
                    } else {
                      setTargetField(e.target.value)
                    }
                  }}
                  className="h-9 text-xs rounded-lg bg-background"
                >
                  <optgroup label="Các trường của Note Type hiện tại">
                    {noteFieldNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </optgroup>
                  <option value="__custom__">✏️ Nhập tên trường mới...</option>
                </NativeSelect>
              ) : (
                <Input
                  value={customTargetName}
                  onChange={(e) => setCustomTargetName(e.target.value)}
                  placeholder="Nhập tên trường lưu (vd: StrokeDiagram)..."
                  className="h-9 text-xs bg-background"
                  autoFocus
                />
              )}
            </div>

            {/* Locale */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Languages className="size-3.5" />
                <span>Quy tắc nét / Ngôn ngữ</span>
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
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1">
                <Code className="size-3.5" />
                <span>Định dạng lưu trữ</span>
              </Label>
              <NativeSelect
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as 'html' | 'raw' | 'urls')}
                className="h-9 text-xs rounded-lg bg-background font-medium"
              >
                <option value="html">HTML bọc &lt;img&gt; (Khuyên dùng - Hiển thị ngay)</option>
                <option value="raw">URL raw (Đường dẫn Image Library - /media/library/...)</option>
                <option value="urls">JSON URLs (Mảng JSON - ["/media/library/..."])</option>
              </NativeSelect>
            </div>
          </div>

          {/* Format helper hint */}
          <div className="p-2.5 rounded-xl bg-primary/5 border border-primary/10 flex items-start gap-2 text-[11px] text-muted-foreground leading-relaxed">
            <Info className="size-3.5 text-primary shrink-0 mt-0.5" />
            <div>
              {outputFormat === 'html' && (
                <span>
                  <strong className="text-foreground font-semibold">HTML Embed:</strong> Sinh thẻ ảnh{' '}
                  <code className="font-mono bg-primary/10 text-primary px-1 py-0.5 rounded text-[10px]">
                    &lt;div class=&quot;flama-stroke-diagram&quot;&gt;&lt;img src=&quot;/media/library/stroke_ja_65e5&quot; .../&gt;&lt;/div&gt;
                  </code>{' '}
                  để hiển thị trực tiếp sơ đồ nét khi ôn tập thẻ trên web và Anki.
                </span>
              )}
              {outputFormat === 'raw' && (
                <span>
                  <strong className="text-foreground font-semibold">URL Raw:</strong> Chỉ lưu chuỗi đường dẫn Image Library{' '}
                  <code className="font-mono bg-primary/10 text-primary px-1 py-0.5 rounded text-[10px]">
                    /media/library/stroke_ja_65e5
                  </code>{' '}
                  (xuống dòng nếu nhiều chữ), phù hợp để tự viết template HTML riêng.
                </span>
              )}
              {outputFormat === 'urls' && (
                <span>
                  <strong className="text-foreground font-semibold">JSON URLs:</strong> Lưu danh sách mảng JSON{' '}
                  <code className="font-mono bg-primary/10 text-primary px-1 py-0.5 rounded text-[10px]">
                    [&quot;/media/library/stroke_ja_65e5&quot;]
                  </code>{' '}
                  cho việc lập trình hoặc tự xử lý dữ liệu nâng cao.
                </span>
              )}
            </div>
          </div>

          {/* Overwrite option */}
          <div className="flex items-center space-x-2 pt-0.5">
            <Checkbox
              id="overwrite-strokes"
              checked={overwrite}
              onCheckedChange={(c) => setOverwrite(Boolean(c))}
            />
            <Label
              htmlFor="overwrite-strokes"
              className="text-xs font-medium cursor-pointer select-none text-foreground"
            >
              Ghi đè nếu trường đích đã có dữ liệu trước đó
            </Label>
          </div>

          {/* Live Preview Area */}
          <div className="space-y-2 pt-2 border-t border-border/60">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Eye className="size-3.5 text-primary" />
                <span>Xem trước kết quả trích xuất từ trường "{sourceField}"</span>
              </span>
              {previewQuery.isFetching && (
                <span className="text-[11px] text-primary flex items-center gap-1 font-medium">
                  <LoaderCircle className="size-3 animate-spin" /> Đang xử lý…
                </span>
              )}
            </div>

            <div className="space-y-1">
              <Input
                value={sampleText}
                onChange={(e) => setSampleText(e.target.value)}
                placeholder={`Nhập văn bản hoặc nội dung trường "${sourceField}"...`}
                className="h-8 text-xs bg-muted/40 font-medium"
              />
              {!sampleText && (
                <p className="text-[11px] text-muted-foreground italic">
                  Trường "{sourceField}" của thẻ đang chọn chưa có nội dung. Bạn có thể gõ chữ trực tiếp vào ô trên để xem thử.
                </p>
              )}
            </div>

            {/* Extracted characters badges */}
            {previewQuery.data?.characters && previewQuery.data.characters.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-[11px] text-muted-foreground mr-0.5">Chữ Hán trích xuất ({previewQuery.data.characters.length}):</span>
                {previewQuery.data.characters.map((c) => (
                  <Badge key={c} variant="secondary" className="text-xs font-bold px-2 py-0.5 bg-primary/10 text-primary border-primary/20">
                    {c}
                  </Badge>
                ))}
              </div>
            )}

            {/* Rendered SVG Preview */}
            <div className="p-3.5 rounded-xl bg-card border border-border/80 min-h-28 flex items-center justify-center shadow-xs">
              {previewQuery.data?.items && previewQuery.data.items.length > 0 ? (
                <div className="flex flex-wrap gap-3.5 justify-center items-center">
                  {previewQuery.data.items.map((item) => (
                    <div
                      key={item.hex}
                      className="w-20 h-20 sm:w-24 sm:h-24 rounded-xl bg-white dark:bg-zinc-950 border border-border/70 p-1 flex items-center justify-center overflow-hidden shadow-2xs hover:border-primary/50 transition-all shrink-0"
                    >
                      <img
                        src={resolveBackendUrl(item.url)}
                        alt={item.char}
                        title={`${item.char} - Thứ tự nét`}
                        className="w-full h-full object-contain"
                        loading="lazy"
                        onError={(e) => {
                          const target = e.target as HTMLImageElement
                          target.onerror = null
                          target.src = resolveBackendUrl('/static/images/image-library-fallback.svg')
                        }}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-muted-foreground text-xs py-3">
                  <AlertCircle className="size-5 mx-auto mb-1 opacity-50" />
                  <span>Không tìm thấy chữ Hán nào trong văn bản để hiển thị thứ tự nét.</span>
                </div>
              )}
            </div>

            {/* Output Code / Text Preview */}
            {previewQuery.data?.output && (
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1 font-medium">
                    <Sparkles className="size-3 text-primary" />
                    <span>Mã sẽ được lưu vào trường &quot;{effectiveTargetField}&quot;:</span>
                  </span>
                  <button
                    type="button"
                    onClick={handleCopyCode}
                    className="flex items-center gap-1 text-primary hover:underline font-semibold"
                  >
                    {copiedCode ? <Check className="size-3" /> : <Copy className="size-3" />}
                    <span>{copiedCode ? 'Đã chép' : 'Sao chép'}</span>
                  </button>
                </div>
                <div className="p-2.5 rounded-lg bg-muted/60 border border-border/60 font-mono text-[11px] text-foreground overflow-x-auto whitespace-pre-wrap break-all max-h-20 select-all">
                  {previewQuery.data.output}
                </div>
              </div>
            )}
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

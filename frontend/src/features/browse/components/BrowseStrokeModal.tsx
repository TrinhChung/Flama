import '@/shared/config/i18n'
import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
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
import {
  Check,
  Layers,
  LoaderCircle,
  PenTool,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi, type GenerateStrokesResponse } from '@/app/api'
import { loadStoredStrokeSettings } from '../services/strokeStorage'
import type { useBrowseState, CardDetailResponse } from '../hooks/useBrowseState'
import { BrowseStrokeSinglePreview } from './BrowseStrokeSinglePreview'
import { BrowseStrokeBatchForm } from './BrowseStrokeBatchForm'

export interface BrowseStrokeModalProps {
  browse?: ReturnType<typeof useBrowseState>
  isOpen: boolean
  onClose: () => void
  mode?: 'single' | 'batch'
  cardId?: string | null
  fields?: Array<{ name: string; field_type?: string }>
  fieldValues?: Record<string, string>
  deckName?: string | null
  onApply?: (targetField: string, value: string) => void
}

export function BrowseStrokeModal({
  browse,
  isOpen,
  onClose,
  mode = 'batch',
  cardId,
  fields,
  fieldValues,
  deckName,
  onApply,
}: BrowseStrokeModalProps) {
  const { t } = useTranslation('browse')
  const defaultQueryClient = useQueryClient()
  const {
    selectedCards = [],
    selectedDeckId,
    activeCardId,
    cards = [],
    decksQuery,
    cardDetailQuery,
    editFieldValues: browseEditFieldValues,
    setEditFieldValues,
    queryClient: browseQueryClient,
  } = browse || {}

  const queryClient = browseQueryClient || defaultQueryClient
  const editFieldValues = browseEditFieldValues || fieldValues || {}

  // Determine target card ID to resolve actual Note Type fields
  const targetCardId =
    cardId || activeCardId || (selectedCards.length > 0 ? selectedCards[0] : cards[0]?.card_id)

  // Fetch card detail for target card if not already active in cardDetailQuery
  const targetCardQuery = useQuery({
    queryKey: ['browse', 'stroke-modal-card-detail', targetCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/browse/cards/${targetCardId}`),
    enabled: isOpen && Boolean(targetCardId) && cardDetailQuery?.data?.card?.card_id !== targetCardId,
    staleTime: 1000 * 60 * 5,
  })

  // Extract actual fields of the Note Type currently in use
  const actualNoteFields = useMemo(() => {
    if (fields && fields.length > 0) {
      return fields
    }
    if (
      Boolean(targetCardId) &&
      cardDetailQuery?.data?.card?.card_id === targetCardId &&
      Boolean(cardDetailQuery?.data?.fields?.length)
    ) {
      return cardDetailQuery.data.fields
    }
    if (targetCardQuery?.data?.fields?.length) {
      return targetCardQuery.data.fields
    }
    if (cardDetailQuery?.data?.fields?.length) {
      return cardDetailQuery.data.fields
    }
    return []
  }, [fields, cardDetailQuery?.data, targetCardQuery?.data, targetCardId])

  const noteFieldNames = useMemo(() => {
    const names = actualNoteFields.map((f) => f.name).filter(Boolean)
    if (names.length > 0) return names
    return ['Expression', 'Reading', 'Meaning', 'StrokeDiagram']
  }, [actualNoteFields])

  const mediaTargetFieldNames = useMemo(
    () =>
      actualNoteFields
        .filter((field) => {
          const type = String(field.field_type || '').toLowerCase()
          if (['image', 'diagram'].includes(type)) return true
          const name = field.name.toLowerCase()
          return [
            'diagram',
            'strokediagram',
            'stroke_diagram',
            'kanjistrokes',
            'strokes',
            'kanji_strokes',
            'stroke',
          ].includes(name)
        })
        .map((field) => field.name)
        .filter(Boolean),
    [actualNoteFields],
  )

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
      mediaTargetFieldNames.find((f) =>
        ['diagram', 'strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes', 'stroke'].includes(
          f.toLowerCase(),
        ),
      ) ||
      (mediaTargetFieldNames.includes('StrokeDiagram')
        ? 'StrokeDiagram'
        : mediaTargetFieldNames[0]) ||
      noteFieldNames.find((f) =>
        ['diagram', 'strokediagram', 'stroke_diagram', 'kanjistrokes', 'strokes', 'kanji_strokes', 'stroke'].includes(
          f.toLowerCase(),
        ),
      ) ||
      ''
    )
  }, [mediaTargetFieldNames, noteFieldNames])

  const [sourceField, setSourceField] = useState(defaultSource)
  const [targetField, setTargetField] = useState(defaultTarget)

  // Sync state when defaults change
  useEffect(() => {
    if (defaultSource && !noteFieldNames.includes(sourceField)) {
      setSourceField(defaultSource)
    }
    if (defaultTarget && (!targetField || (!mediaTargetFieldNames.includes(targetField) && !noteFieldNames.includes(targetField)))) {
      setTargetField(defaultTarget)
    }
  }, [defaultSource, defaultTarget, noteFieldNames, mediaTargetFieldNames, sourceField, targetField])

  // Resolve actual text content from the selected sourceField across active/target card data
  const resolvedSourceValue = useMemo(() => {
    // 1. From active sidebar edits
    if (
      editFieldValues[sourceField] !== undefined &&
      editFieldValues[sourceField] !== null &&
      String(editFieldValues[sourceField]).trim()
    ) {
      return String(editFieldValues[sourceField]).trim()
    }
    // 2. From active card note field_values
    const cardNoteFieldVal = cardDetailQuery?.data?.note?.field_values?.[sourceField]
    if (
      cardNoteFieldVal !== undefined &&
      cardNoteFieldVal !== null &&
      String(cardNoteFieldVal).trim()
    ) {
      return String(cardNoteFieldVal).trim()
    }
    // 3. From target card query note field_values
    const targetNoteFieldVal = targetCardQuery?.data?.note?.field_values?.[sourceField]
    if (
      targetNoteFieldVal !== undefined &&
      targetNoteFieldVal !== null &&
      String(targetNoteFieldVal).trim()
    ) {
      return String(targetNoteFieldVal).trim()
    }
    // 4. Fallback from card row
    const matchingCard =
      (targetCardId ? cards.find((c) => c.card_id === targetCardId) : undefined) || cards[0]
    if (matchingCard) {
      const lower = sourceField.toLowerCase()
      if (
        ['expression', 'word', 'kanji', 'hanzi', 'vocab', 'vocabulary', 'front'].includes(lower) &&
        matchingCard.word
      ) {
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
    cardDetailQuery?.data,
    targetCardQuery?.data,
    cards,
    targetCardId,
  ])

  // Auto-detect initial locale based on deck name or character composition
  const detectedLocale = useMemo(() => {
    const effectiveDeckName = (
      deckName ||
      decksQuery?.data?.decks?.find((d) => d.id === selectedDeckId)?.name ||
      cardDetailQuery?.data?.note?.deck_name ||
      (targetCardId ? cards.find((c) => c.card_id === targetCardId)?.deck_name : undefined) ||
      ''
    ).toLowerCase()
    if (/hsk|trung|chinese|hán|zh/i.test(effectiveDeckName)) {
      return 'zh-CN'
    }
    if (/kanji|n[1-5]|nhật|japanese|ja/i.test(effectiveDeckName)) {
      return 'ja'
    }
    if (/[汉语话书买卖时间门关开钱鸡车电习爱国难易简单红蓝绿颜]/i.test(resolvedSourceValue)) {
      return 'zh-CN'
    }
    if (/[漢語話書買賣門關開錢雞車電習愛國學問題幫讓歲還過難練結發經動歡館銀飛機紅藍綠認識邊遠進鐘點課運遊體會讀寫聽說對應當從義號樣這裡頭視後廣風傳節圖與計劃網東長變報選請導備準確龍鳳華歷歸業農種標環構營製質達議組務調設實際處積極績術複雜職]/.test(resolvedSourceValue)) {
      return 'zh-TW'
    }
    return 'ja'
  }, [deckName, decksQuery?.data?.decks, cardDetailQuery?.data, cards, selectedDeckId, targetCardId, resolvedSourceValue])

  const [locale, setLocale] = useState<'ja' | 'zh-CN' | 'zh-TW'>(() => {
    return loadStoredStrokeSettings().locale
  })

  // Always auto-detect locale based on current deck/card content when modal opens
  useEffect(() => {
    if (detectedLocale) {
      setLocale(detectedLocale as 'ja' | 'zh-CN' | 'zh-TW')
    }
  }, [detectedLocale])

  const [overwrite, setOverwrite] = useState(() => {
    return loadStoredStrokeSettings().overwrite
  })
  const [maxChars] = useState(15)
  const [copiedCode, setCopiedCode] = useState(false)

  const [sampleText, setSampleText] = useState(resolvedSourceValue)

  // Automatically update sampleText whenever sourceField, target card, or card data changes
  useEffect(() => {
    setSampleText(resolvedSourceValue)
  }, [resolvedSourceValue, sourceField])

  // Stroke preview query
  const previewQuery = useQuery<GenerateStrokesResponse>({
    queryKey: ['stroke-preview', sampleText, locale, maxChars],
    queryFn: () =>
      appApi.generateStrokes({
        text: sampleText,
        locale,
        format: 'raw',
        max_characters: maxChars,
      }),
    enabled: isOpen && Boolean(sampleText.trim()),
    staleTime: 1000 * 60 * 5,
  })

  const targetCardIds = mode === 'single' && cardId ? [cardId] : selectedCards

  // Estimate batch workload query
  const estimateQuery = useQuery({
    queryKey: [
      'stroke-estimate',
      mode,
      targetCardIds,
      selectedDeckId,
      sourceField,
      targetField,
      locale,
      overwrite,
      maxChars,
    ],
    queryFn: () =>
      appApi.estimateBatchStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        card_ids: targetCardIds.length ? targetCardIds : undefined,
        overwrite,
        max_characters: maxChars,
      }),
    enabled: isOpen && mode !== 'single' && Boolean(sourceField.trim() && targetField.trim()),
    staleTime: 1000 * 30,
  })

  // Batch generate mutation
  const batchMutation = useMutation({
    mutationFn: () => {
      if (!sourceField.trim()) {
        throw new Error(t('stroke_modal.errors.select_source'))
      }
      if (!targetField) {
        throw new Error(t('stroke_modal.errors.select_target'))
      }

      return appApi.batchGenerateStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        card_ids: targetCardIds.length ? targetCardIds : undefined,
        format: 'raw',
        overwrite,
        max_characters: maxChars,
      })
    },
    onSuccess: (res) => {
      const updatedText =
        res.updated > 0
          ? t('stroke_modal.toasts.updated_success', { count: res.updated })
          : t('stroke_modal.toasts.completed_check')
      const skippedNote = res.skipped > 0 ? t('stroke_modal.toasts.skipped_suffix', { count: res.skipped }) : ''
      toast.success(`${updatedText}${skippedNote}`)
      void queryClient.invalidateQueries({ queryKey: ['browse-cards'] })
      void queryClient.invalidateQueries({ queryKey: ['card-detail'] })
      onClose()
    },
    onError: (err: any) => {
      toast.error(
        err?.message || t('stroke_modal.errors.cannot_generate'),
      )
    },
  })

  const handleApplySingle = () => {
    if (!targetField) {
      toast.error(t('stroke_modal.errors.select_target'))
      return
    }
    if (previewQuery.data?.output) {
      const canonicalUrls = (previewQuery.data.items || [])
        .map((item) => String(item.url || '').trim())
        .filter(Boolean)
        .join('\n')
      if (onApply) {
        onApply(targetField, canonicalUrls)
      } else if (setEditFieldValues) {
        setEditFieldValues((prev) => ({
          ...prev,
          [targetField]: canonicalUrls,
        }))
      }
      toast.success(t('stroke_modal.toasts.applied_single', { field: targetField }))
      onClose()
    } else {
      toast.warning(t('stroke_modal.errors.no_kanji'))
    }
  }

  const handleCopyCode = async () => {
    if (!previewQuery.data?.output) return
    try {
      await navigator.clipboard.writeText(previewQuery.data.output)
      setCopiedCode(true)
      toast.success(t('stroke_modal.toasts.copied_clipboard'))
      setTimeout(() => setCopiedCode(false), 2000)
    } catch {
      toast.error(t('stroke_modal.errors.cannot_copy'))
    }
  }

  const isDeckScope = mode === 'batch' && selectedCards.length === 0 && Boolean(selectedDeckId)
  const selectedDeck = browse?.selectedDeck
  const isMixedNoteTypes =
    isDeckScope &&
    (Boolean(selectedDeck?.has_mixed_note_types) || Boolean(estimateQuery.data?.has_mixed_note_types))

  const targetCount =
    mode === 'single'
      ? 1
      : selectedCards.length > 0
        ? selectedCards.length
        : selectedDeck
          ? t('stroke_modal.entire_deck_scope', {
              name: selectedDeck.name,
              count: selectedDeck.counts?.total ?? 'tất cả',
            })
          : t('stroke_modal.all_cards_in_deck')

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[92vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold text-foreground">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <PenTool className="size-4.5 shrink-0" />
            </div>
            <span>{t('stroke_modal.title')}</span>
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            {t('stroke_modal.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {/* Target summary badge */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-muted/50 border border-border/60">
            <span className="text-muted-foreground flex items-center gap-1.5 font-medium">
              <Layers className="size-3.5 text-primary" />
              <span>{t('stroke_modal.scope_label')}</span>
            </span>
            <Badge variant="secondary" className="font-bold text-xs">
              {typeof targetCount === 'number' ? t('stroke_modal.cards_count', { count: targetCount }) : targetCount}
            </Badge>
          </div>

          <BrowseStrokeBatchForm
            isMixedNoteTypes={isMixedNoteTypes}
            selectedDeck={selectedDeck}
            sourceField={sourceField}
            setSourceField={setSourceField}
            targetField={targetField}
            setTargetField={setTargetField}
            noteFieldNames={noteFieldNames}
            mediaTargetFieldNames={mediaTargetFieldNames}
            locale={locale}
            setLocale={setLocale}
            overwrite={overwrite}
            setOverwrite={setOverwrite}
            mode={mode}
            estimateQuery={estimateQuery}
          />

          <BrowseStrokeSinglePreview
            sourceField={sourceField}
            targetField={targetField}
            sampleText={sampleText}
            setSampleText={setSampleText}
            previewQuery={previewQuery}
            copiedCode={copiedCode}
            handleCopyCode={handleCopyCode}
          />
        </div>

        <DialogFooter className="px-5 py-3 border-t bg-muted/20 flex flex-row items-center justify-end gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={onClose} className="h-9 text-xs rounded-xl">
            {t('stroke_modal.close')}
          </Button>

          {mode === 'single' ? (
            <Button
              size="sm"
              onClick={handleApplySingle}
              disabled={!targetField || !previewQuery.data?.items?.length}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              <Check className="size-3.5" />
              <span>{t('stroke_modal.add_to_card')}</span>
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => batchMutation.mutate()}
              disabled={!targetField || batchMutation.isPending || isMixedNoteTypes}
              className="h-9 text-xs font-bold rounded-xl gap-1.5 shadow-xs"
            >
              {batchMutation.isPending ? (
                <>
                  <LoaderCircle className="size-3.5 animate-spin" />
                  <span>
                    {t('stroke_modal.generating', {
                      eta: estimateQuery.data?.estimated_human ? `(${estimateQuery.data.estimated_human})` : '',
                    })}
                  </span>
                </>
              ) : (
                <>
                  <PenTool className="size-3.5" />
                  <span>
                    {t('stroke_modal.generate_for_cards', {
                      target: typeof targetCount === 'number' ? t('stroke_modal.cards_count', { count: targetCount }) : targetCount,
                    })}
                  </span>
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

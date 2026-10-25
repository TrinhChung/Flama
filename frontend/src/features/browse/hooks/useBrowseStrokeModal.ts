import { useState, useEffect, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import type { GenerateStrokesResponse } from '@/entities/stroke'
import { fieldValueEditorText } from '@/entities/flashcard/fields'
import { browseApi } from '../api/browseApi'
import { browseQueryKeys } from '../api/browseQueryKeys'
import { strokeApi } from '../api/strokeApi'
import { loadStoredStrokeSettings } from '../services/strokeStorage'
import type { BrowseStrokeModalProps } from '../model/strokeModal'

const EMPTY_FIELD_VALUES: Record<string, unknown> = {}

export function useBrowseStrokeModal({
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
  const isDeckScope = mode === 'batch' && selectedCards.length === 0 && Boolean(selectedDeckId)
  const selectedDeck = browse?.selectedDeck
  const summaryPending = isDeckScope && Boolean(browse) && (!selectedDeck || selectedDeck.summary_loaded === false)
  const editFieldValues = browseEditFieldValues || fieldValues || EMPTY_FIELD_VALUES

  // Determine target card ID to resolve actual Note Type fields
  const targetCardId =
    cardId || activeCardId || (selectedCards.length > 0 ? selectedCards[0] : cards[0]?.card_id)

  // Fetch card detail for target card if not already active in cardDetailQuery
  const targetCardQuery = useQuery({
    queryKey: browseQueryKeys.detail(targetCardId),
    queryFn: ({ signal }) => browseApi.fetchCardDetail(targetCardId!, signal),
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
      fieldValueEditorText(editFieldValues[sourceField]).trim()
    ) {
      return fieldValueEditorText(editFieldValues[sourceField]).trim()
    }
    // 2. From active card note field_values
    const cardNoteFieldVal = cardDetailQuery?.data?.note?.field_values?.[sourceField]
    if (
      cardNoteFieldVal !== undefined &&
      cardNoteFieldVal !== null &&
      fieldValueEditorText(cardNoteFieldVal).trim()
    ) {
      return fieldValueEditorText(cardNoteFieldVal).trim()
    }
    // 3. From target card query note field_values
    const targetNoteFieldVal = targetCardQuery?.data?.note?.field_values?.[sourceField]
    if (
      targetNoteFieldVal !== undefined &&
      targetNoteFieldVal !== null &&
      fieldValueEditorText(targetNoteFieldVal).trim()
    ) {
      return fieldValueEditorText(targetNoteFieldVal).trim()
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
      strokeApi.generateStrokes({
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
      strokeApi.estimateBatchStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        ...(browse ? { note_ids: targetCardIds.length ? targetCardIds : undefined } : { card_ids: targetCardIds.length ? targetCardIds : undefined }),
        overwrite,
        max_characters: maxChars,
      }),
    enabled: isOpen && mode !== 'single' && !summaryPending && Boolean(sourceField.trim() && targetField.trim()),
    staleTime: 1000 * 30,
  })

  // Batch generate mutation
  const batchMutation = useMutation({
    mutationFn: () => {
      if (summaryPending || selectedDeck?.has_mixed_note_types) throw new Error(t('toasts.mixed_note_types_error'))
      if (!sourceField.trim()) {
        throw new Error(t('stroke_modal.errors.select_source'))
      }
      if (!targetField) {
        throw new Error(t('stroke_modal.errors.select_target'))
      }

      return strokeApi.batchGenerateStrokes({
        source_field: sourceField,
        target_field: targetField,
        locale,
        deck_id: !targetCardIds.length && selectedDeckId ? selectedDeckId : undefined,
        ...(browse ? { note_ids: targetCardIds.length ? targetCardIds : undefined } : { card_ids: targetCardIds.length ? targetCardIds : undefined }),
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
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail'] })
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

  return { isOpen, onClose, mode, t, noteFieldNames, mediaTargetFieldNames, sourceField, setSourceField, targetField, setTargetField, locale, setLocale, overwrite, setOverwrite, copiedCode, sampleText, setSampleText, previewQuery, estimateQuery, batchMutation, handleApplySingle, handleCopyCode, selectedDeck, isMixedNoteTypes, summaryPending, targetCount }
}

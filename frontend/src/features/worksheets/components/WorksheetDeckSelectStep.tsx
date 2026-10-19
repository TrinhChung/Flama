import React, { useState, useMemo, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  FolderTree,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  ArrowRight,
  Info,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { apiRequest } from '@/shared/api/client'
import {
  DeckSelectionTreeView,
  type DeckOption,
} from '@/entities/deck/ui/DeckSelectionTreeView'
import { fetchDeckWorksheetMeta } from '../api'
import type { DeckWorksheetMeta } from '../types'

export interface SimpleDeck {
  id: number
  name: string
  parent_id?: number | null
  path?: string
  counts?: { total?: number; new?: number; learn?: number; due?: number }
}

export interface WorksheetDeckSelectStepProps {
  selectedDeckId: number | null
  onSelectDeck: (deckId: number, meta: DeckWorksheetMeta) => void
  onSelectStandalone: () => void
  onCancel?: () => void
  className?: string
}

export const WorksheetDeckSelectStep: React.FC<WorksheetDeckSelectStepProps> = ({
  selectedDeckId,
  onSelectDeck,
  onSelectStandalone,
  onCancel,
  className = '',
}) => {
  const { t } = useTranslation('worksheets')
  const [activeDeckId, setActiveDeckId] = useState<number | null>(selectedDeckId)
  const [deckMeta, setDeckMeta] = useState<DeckWorksheetMeta | null>(null)
  const [isLoadingMeta, setIsLoadingMeta] = useState<boolean>(false)
  const [metaError, setMetaError] = useState<string | null>(null)

  // 1. Fetch accessible deck list
  const { data: rawDecks = [], isLoading: isLoadingDecks } = useQuery({
    queryKey: ['browse-decks-tree'],
    queryFn: async () => {
      const res = await apiRequest<{ decks: SimpleDeck[] }>('/api/browse/decks')
      return res.decks || []
    },
    staleTime: 60 * 1000,
  })

  // Format decks for DeckSelectionTreeView
  const deckOptions: DeckOption[] = useMemo(() => {
    const deckMap = new Map<number, SimpleDeck>()
    rawDecks.forEach((d) => deckMap.set(d.id, d))

    const buildPath = (deck: SimpleDeck): string => {
      const parts = [deck.name]
      let cur = deck
      const seen = new Set<number>()
      while (cur.parent_id != null && deckMap.has(cur.parent_id) && !seen.has(cur.parent_id)) {
        seen.add(cur.parent_id)
        cur = deckMap.get(cur.parent_id)!
        parts.unshift(cur.name)
      }
      return parts.join('::')
    }

    return rawDecks.map((d) => ({
      id: d.id,
      name: d.name,
      path: d.path || buildPath(d),
      parent_id: d.parent_id,
      notes_count: d.counts?.total ?? d.counts?.due ?? 0,
    }))
  }, [rawDecks])

  // 2. Fetch metadata whenever a deck is selected
  useEffect(() => {
    if (!activeDeckId) {
      setDeckMeta(null)
      setMetaError(null)
      return
    }

    let isMounted = true
    setIsLoadingMeta(true)
    setMetaError(null)

    fetchDeckWorksheetMeta(activeDeckId)
      .then((meta) => {
        if (!isMounted) return
        setDeckMeta(meta)
      })
      .catch((err) => {
        if (!isMounted) return
        setMetaError(String(err?.message || err || 'Không thể tải thông tin bộ thẻ'))
      })
      .finally(() => {
        if (isMounted) setIsLoadingMeta(false)
      })

    return () => {
      isMounted = false
    }
  }, [activeDeckId])

  // Validation rules:
  // Deck must have exactly 1 note type
  const hasMultipleNoteTypes = Boolean(
    deckMeta && (deckMeta.has_mixed_note_types || (deckMeta.note_types && deckMeta.note_types.length > 1))
  )
  const isEmptyDeck = Boolean(deckMeta && deckMeta.total_notes === 0)
  const canProceed = Boolean(
    activeDeckId && deckMeta && !hasMultipleNoteTypes && !isEmptyDeck && !isLoadingMeta
  )

  const handleConfirm = () => {
    if (canProceed && activeDeckId && deckMeta) {
      onSelectDeck(activeDeckId, deckMeta)
    }
  }

  return (
    <div className={`flex flex-col h-full overflow-hidden ${className}`}>
      {/* Header Description */}
      <div className="p-4 border-b border-border/70 bg-card/60 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
              <FolderTree className="size-4 text-primary" />
              <span>{t('deck_select.header_title', 'Bước 1: Chọn bộ thẻ để xuất bài tập')}</span>
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {t('deck_select.header_desc', 'Chọn bộ thẻ chứa từ vựng hoặc chữ Hán bạn muốn tạo mẫu giấy luyện viết & in ấn.')}
            </p>
          </div>
          <Badge variant="outline" className="text-[11px] font-semibold">
            {t('deck_select.deck_count', '{{count}} bộ thẻ', { count: deckOptions.length })}
          </Badge>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Standalone Option Card */}
        <div
          onClick={onSelectStandalone}
          className="p-3.5 rounded-xl border-2 border-dashed border-primary/40 bg-primary/5 hover:bg-primary/10 hover:border-primary cursor-pointer transition-all flex items-center justify-between group"
        >
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-lg bg-primary/15 text-primary flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
              <FileText className="size-4.5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-xs font-bold text-foreground">
                  {t('deck_select.standalone_card_title', 'Tạo mẫu giấy in tự do (Không cần thẻ học)')}
                </h4>
                <Badge variant="secondary" className="text-[9.5px] px-1.5 py-0 font-semibold bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/20">
                  {t('deck_select.standalone_card_badge', 'Genkō Yōshi / Ô kẻ tay')}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                {t('deck_select.standalone_card_desc', 'In trang trắng giấy làm văn 400 ô, ô chữ Hán hoa thị, chữ thập để tự do viết tay bằng bút mực.')}
              </p>
            </div>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 text-xs font-semibold text-primary group-hover:translate-x-0.5 transition-transform shrink-0"
          >
            <span>{t('deck_select.standalone_card_action', 'Chọn mẫu tự do →')}</span>
          </Button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="h-px bg-border/80 flex-1" />
          <span className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
            {t('deck_select.divider_or', 'Hoặc chọn từ bộ thẻ của bạn')}
          </span>
          <div className="h-px bg-border/80 flex-1" />
        </div>

        {/* Deck Tree View */}
        <div className="rounded-xl border border-border/80 bg-card p-3 shadow-2xs">
          {isLoadingDecks ? (
            <div className="h-48 flex flex-col items-center justify-center gap-2 text-muted-foreground">
              <Loader2 className="size-6 animate-spin text-primary" />
              <span className="text-xs">{t('deck_select.loading_decks', 'Đang tải danh sách bộ thẻ...')}</span>
            </div>
          ) : deckOptions.length === 0 ? (
            <div className="h-36 flex flex-col items-center justify-center gap-2 text-muted-foreground text-center">
              <FolderTree className="size-8 opacity-40" />
              <p className="text-xs font-medium">{t('deck_select.empty_decks', 'Chưa có bộ thẻ nào.')}</p>
            </div>
          ) : (
            <div className="max-h-[260px] overflow-y-auto">
              <DeckSelectionTreeView
                deckOptions={deckOptions}
                selectedDeckId={activeDeckId ? String(activeDeckId) : ''}
                onSelectDeck={(id: string) => setActiveDeckId(Number(id))}
              />
            </div>
          )}
        </div>

        {/* Selected Deck Metadata & Validation Feedback */}
        {isLoadingMeta && (
          <div className="p-3 rounded-xl border border-border/60 bg-muted/30 flex items-center gap-2.5 text-xs text-muted-foreground">
            <Loader2 className="size-4 animate-spin text-primary shrink-0" />
            <span>{t('deck_select.checking_structure', 'Đang kiểm tra cấu trúc loại thẻ của bộ thẻ...')}</span>
          </div>
        )}

        {metaError && (
          <div className="p-3 rounded-xl border border-destructive/30 bg-destructive/10 flex items-center gap-2.5 text-xs text-destructive">
            <AlertTriangle className="size-4 shrink-0" />
            <span>{metaError}</span>
          </div>
        )}

        {deckMeta && !isLoadingMeta && (
          <>
            {/* Case 1: Deck has >= 2 note types -> BLOCK & SHOW DETAILED NOTICE */}
            {hasMultipleNoteTypes && (
              <div className="p-3.5 rounded-xl border-2 border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 space-y-2">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="size-4.5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-bold text-amber-950 dark:text-amber-100">
                      {t('deck_select.mixed_note_types_title', 'Không thể tiếp tục: Bộ thẻ chứa {{count}} loại thẻ khác nhau', { count: deckMeta.note_types?.length || 2 })}
                    </h4>
                    <p className="text-[11px] text-amber-800 dark:text-amber-300 mt-1 leading-relaxed">
                      {t('deck_select.mixed_note_types_desc', 'Để hệ thống ánh xạ dữ liệu và trích xuất chữ Hán chính xác, bộ thẻ phải đồng nhất duy nhất 1 loại thẻ (Note Type).')}
                    </p>
                    <div className="mt-2 space-y-1 bg-background/60 p-2 rounded-lg border border-amber-500/20 text-[11px]">
                      <div className="font-semibold text-foreground">
                        {t('deck_select.detected_note_types', 'Các loại thẻ phát hiện trong bộ thẻ này:')}
                      </div>
                      <ul className="list-disc list-inside space-y-0.5 text-muted-foreground">
                        {deckMeta.note_types?.map((nt) => (
                          <li key={nt.id}>
                            <span className="font-medium text-foreground">{nt.name}</span> ({t('deck_select.note_count_parens', '{{count}} ghi chú', { count: nt.note_count })})
                          </li>
                        ))}
                      </ul>
                    </div>
                    <p className="text-[10.5px] font-semibold text-amber-700 dark:text-amber-300 mt-2">
                      {t('deck_select.mixed_note_types_hint', '👉 Vui lòng chọn một bộ thẻ con cụ thể hoặc bộ thẻ khác chỉ có 1 loại thẻ duy nhất.')}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Case 2: Deck is empty */}
            {isEmptyDeck && (
              <div className="p-3.5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-200 flex items-start gap-2.5 text-xs">
                <Info className="size-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <div className="font-bold">{t('deck_select.empty_deck_title', 'Bộ thẻ này hiện chưa có ghi chú nào')}</div>
                  <div className="text-[11px] text-muted-foreground mt-0.5">
                    {t('deck_select.empty_deck_desc', 'Vui lòng thêm thẻ vào bộ thẻ hoặc chọn bộ thẻ khác có sẵn dữ liệu để tạo bài tập.')}
                  </div>
                </div>
              </div>
            )}

            {/* Case 3: Deck is valid and ready! */}
            {!hasMultipleNoteTypes && !isEmptyDeck && (
              <div className="p-3.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-900 dark:text-emerald-200 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2.5 min-w-0">
                  <CheckCircle2 className="size-4.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-foreground truncate">
                      {deckMeta.deck_name}
                    </div>
                    <div className="text-[11px] text-muted-foreground flex items-center gap-2 flex-wrap mt-0.5">
                      <span>{t('deck_select.total_notes_badge', '{{count}} ghi chú', { count: deckMeta.total_notes })}</span>
                      <span>&bull;</span>
                      <span>{t('deck_select.note_type_label', 'Loại thẻ:')} <strong>{deckMeta.note_types[0]?.name}</strong></span>
                      <span>&bull;</span>
                      <span>{t('deck_select.fields_count', '{{count}} trường dữ liệu', { count: deckMeta.note_types[0]?.fields?.length || 0 })}</span>
                    </div>
                  </div>
                </div>
                <Badge variant="outline" className="bg-emerald-500/20 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 text-[10px] font-bold shrink-0">
                  {t('deck_select.valid_badge', 'Hợp lệ')}
                </Badge>
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer Actions */}
      <div className="p-3.5 border-t border-border/80 bg-muted/30 flex items-center justify-between gap-2 shrink-0">
        {onCancel && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onCancel}
            className="h-9 px-3 text-xs"
          >
            {t('deck_select.close_button', 'Đóng')}
          </Button>
        )}
        <div className="flex items-center gap-2 ml-auto">
          <Button
            type="button"
            size="sm"
            disabled={!canProceed}
            onClick={handleConfirm}
            className="h-9 px-4 text-xs font-bold gap-1.5 bg-primary hover:bg-primary/90 text-primary-foreground shadow-xs"
          >
            <span>{t('deck_select.next_step', 'Tiếp tục: Ánh xạ dữ liệu')}</span>
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
}

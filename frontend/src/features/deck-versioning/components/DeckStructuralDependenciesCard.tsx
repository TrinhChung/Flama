import { useMemo } from 'react'
import { AlertTriangle, CheckCircle2, ExternalLink, Layers, LayoutTemplate } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { DependencyStatusBadge } from './DependencyStatusBadge'
import type { DeckStructuralDependenciesCardProps } from '../model/types'

export function DeckStructuralDependenciesCard({
  deckTitle,
  currentVersionLabel,
  noteTypes,
  isLoading = false,
  onNavigateToNoteType,
  onNavigateToTemplate,
  className,
}: DeckStructuralDependenciesCardProps) {
  const hasStructuralIssues = useMemo(
    () =>
      noteTypes.some(
        (nt) =>
          nt.status === 'update_available' ||
          nt.status === 'draft_changes' ||
          nt.has_draft_changes ||
          nt.templates.some(
            (tpl) =>
              tpl.status === 'update_available' ||
              tpl.status === 'draft_changes' ||
              tpl.has_newer_release ||
              tpl.has_uncommitted_draft
          )
      ),
    [noteTypes]
  )

  if (isLoading) {
    return (
      <Card className="p-6 text-center text-sm text-muted-foreground animate-pulse rounded-2xl border-border/80">
        Đang kiểm tra phụ thuộc cấu trúc…
      </Card>
    )
  }

  return (
    <Card className={className ?? 'overflow-hidden border-border/80 rounded-2xl bg-card'}>
      <CardHeader className="bg-muted/15 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-primary" />
            <CardTitle className="text-base font-semibold">
              Phụ thuộc Cấu trúc (Note Types & Templates)
            </CardTitle>
          </div>
          <div className="flex items-center gap-2">
            {currentVersionLabel && (
              <Badge variant="outline" className="font-mono text-xs">
                {currentVersionLabel}
              </Badge>
            )}
            {hasStructuralIssues ? (
              <Badge
                variant="outline"
                className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 gap-1"
              >
                <AlertTriangle className="size-3" />
                <span>Cần cập nhật cấu trúc</span>
              </Badge>
            ) : (
              <Badge
                variant="secondary"
                className="gap-1 text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-500/30"
              >
                <CheckCircle2 className="size-3 text-emerald-600 dark:text-emerald-400" />
                <span>Đã đồng bộ hoàn toàn</span>
              </Badge>
            )}
          </div>
        </div>
        <CardDescription className="text-xs">
          Bộ thẻ: <span className="font-medium text-foreground break-words" title={deckTitle}>{deckTitle}</span>. Các Loại thẻ và Mẫu
          thẻ được đóng băng bất biến trong bản phát hành này. Kiểm tra phiên bản trước khi công bố.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {noteTypes.length === 0 ? (
          <div className="p-4 text-center text-xs text-muted-foreground border rounded-xl bg-muted/10">
            Không có Loại thẻ nào trong bộ thẻ này.
          </div>
        ) : (
          noteTypes.map((nt) => {
            const hasNewerVersion =
              Boolean(nt.latest_version_label) && nt.latest_version_label !== nt.pinned_version_label

            return (
              <div
                key={nt.note_type_id}
                data-testid={`note-type-item-${nt.note_type_id}`}
                className="rounded-xl border bg-card p-3 sm:p-4 space-y-3 transition-colors hover:border-border"
              >
                {/* Note Type Header */}
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="font-semibold text-sm text-foreground truncate max-w-[200px] sm:max-w-xs"
                      title={nt.note_type_name}
                    >
                      {nt.note_type_name}
                    </span>
                    <span className="text-xs text-muted-foreground">({nt.note_count} thẻ)</span>
                    <Badge variant="outline" className="text-[10px] h-4 font-mono">
                      pin: {nt.pinned_version_label || 'Chưa ghim'}
                    </Badge>
                    {hasNewerVersion && (
                      <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400">
                        Mới nhất: {nt.latest_version_label}
                      </span>
                    )}
                    <DependencyStatusBadge status={nt.status} size="sm" />
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-8 sm:h-7 text-xs gap-1 text-muted-foreground hover:text-foreground"
                    data-testid={`navigate-note-type-${nt.note_type_id}`}
                    onClick={(e) => {
                      if (onNavigateToNoteType) {
                        e.preventDefault()
                        onNavigateToNoteType(nt.note_type_id)
                      }
                    }}
                    asChild={!onNavigateToNoteType}
                  >
                    {onNavigateToNoteType ? (
                      <>
                        <span>Quản lý Loại thẻ</span>
                        <ExternalLink className="size-3" />
                      </>
                    ) : (
                      <a href={`/note-types/${nt.note_type_id}`} target="_blank" rel="noreferrer">
                        <span>Quản lý Loại thẻ</span>
                        <ExternalLink className="size-3" />
                      </a>
                    )}
                  </Button>
                </div>

                {/* Attached Templates section */}
                {nt.templates.length > 0 && (
                  <div className="space-y-1.5 pl-3 border-l-2 border-primary/20">
                    <div className="text-[11px] font-medium text-muted-foreground">
                      Mẫu thẻ gắn kèm:
                    </div>
                    {nt.templates.map((tpl) => {
                      const tplHasNewer =
                        Boolean(tpl.latest_version_label) &&
                        tpl.latest_version_label !== tpl.pinned_version_label

                      return (
                        <div
                          key={tpl.template_id}
                          data-testid={`template-item-${tpl.template_id}`}
                          className="flex flex-wrap items-center justify-between text-xs py-1.5 px-3 rounded-lg bg-muted/30 gap-2"
                        >
                          <div className="flex flex-wrap items-center gap-2">
                            <LayoutTemplate className="size-3.5 text-muted-foreground shrink-0" />
                            <span
                              className="font-medium text-foreground truncate max-w-[180px] sm:max-w-xs"
                              title={tpl.template_name}
                            >
                              {tpl.template_name}
                            </span>
                            {tpl.occurrence_key && (
                              <span className="text-[10px] text-muted-foreground font-mono">
                                [{tpl.occurrence_key}]
                              </span>
                            )}
                            <Badge variant="outline" className="text-[10px] h-4 font-mono">
                              pin: {tpl.pinned_version_label || 'Chưa ghim'}
                            </Badge>
                            {tplHasNewer && (
                              <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400">
                                Mới nhất: {tpl.latest_version_label}
                              </span>
                            )}
                            <DependencyStatusBadge status={tpl.status} size="sm" />
                          </div>

                          <Button
                            variant="link"
                            size="sm"
                            className="h-7 sm:h-6 py-1 px-1 text-xs text-primary gap-1"
                            data-testid={`navigate-template-${tpl.template_id}`}
                            onClick={(e) => {
                              if (onNavigateToTemplate) {
                                e.preventDefault()
                                onNavigateToTemplate(tpl.template_id)
                              }
                            }}
                            asChild={!onNavigateToTemplate}
                          >
                            {onNavigateToTemplate ? (
                              <>
                                <span>Xem mẫu thẻ</span>
                                <ExternalLink className="size-2.5" />
                              </>
                            ) : (
                              <a
                                href={`/card-templates/${tpl.template_id}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                <span>Xem mẫu thẻ</span>
                                <ExternalLink className="size-2.5" />
                              </a>
                            )}
                          </Button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })
        )}
      </CardContent>
    </Card>
  )
}

import type { MouseEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Layers, List } from 'lucide-react'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Page } from '@/shared/components/Page'
import { cn } from '@/lib/utils'

export type NoteTypeSetupShellProps = {
  noteTypeId: string
  name: string
  activeTab: 'fields' | 'templates'
  fieldCount?: number
  templateCount?: number
  children: ReactNode
  actions?: ReactNode
  onNavigate?: (to: string) => void
  /** Fill the viewport height on desktop so a workspace child can use `lg:flex-1`. */
  fill?: boolean
  /** Override the back link target (default: '/flashcards/note-types') */
  backTo?: string
  /** Override the back button label (default: t('setup.back')) */
  backLabel?: string
  /** Secondary breadcrumb / context label (e.g. note type name when editing a template mapping) */
  contextLabel?: string
  /** Optional badge next to title */
  titleBadge?: ReactNode
  /** If true, hides description to save vertical space */
  hideDescription?: boolean
}

export function NoteTypeSetupShell({
  noteTypeId,
  name,
  activeTab,
  fieldCount,
  templateCount,
  children,
  actions,
  onNavigate,
  fill = false,
  backTo,
  backLabel,
  contextLabel,
  titleBadge,
  hideDescription = false,
}: NoteTypeSetupShellProps) {
  const { t } = useTranslation('note_types')
  const tabs = [
    { id: 'fields', label: t('setup.fields_tab'), count: fieldCount, icon: List },
    { id: 'templates', label: t('setup.templates_tab'), count: templateCount, icon: Layers },
  ] as const
  const followLink = (event: MouseEvent<HTMLAnchorElement>, to: string) => {
    if (onNavigate && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button === 0) {
      event.preventDefault()
      onNavigate(to)
    }
  }

  const effectiveBackTo = backTo ?? '/flashcards/note-types'
  const effectiveBackLabel = backLabel ?? t('setup.back')

  return (
    <Page size="full" fill={fill} className={cn('px-3 sm:px-6 lg:px-8 py-3.5 sm:py-5', fill ? 'space-y-3 sm:space-y-4 [--page-fill-min:56rem]' : 'space-y-4 sm:space-y-5')}>
      <AmbientBackground intensity="subtle" />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-xs sm:text-sm text-muted-foreground min-w-0">
          <Button variant="ghost" size="sm" asChild className="-ml-2 h-8 gap-1.5 px-2 text-muted-foreground hover:text-foreground">
            <Link to={effectiveBackTo} onClick={(event) => followLink(event, effectiveBackTo)}>
              <ArrowLeft className="size-4 shrink-0" />
              <span className="truncate">{effectiveBackLabel}</span>
            </Link>
          </Button>
          {contextLabel && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground/80 truncate">
              <span className="text-muted-foreground/40 shrink-0">/</span>
              <span className="font-medium truncate max-w-[140px] sm:max-w-xs">{contextLabel}</span>
            </span>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className={cn('font-bold tracking-tight text-foreground truncate', hideDescription ? 'text-xl sm:text-2xl' : 'text-2xl md:text-3xl')}>{name}</h1>
            {titleBadge}
          </div>
          {!hideDescription && (
            <p className="max-w-3xl text-sm text-muted-foreground md:text-base">
              {t('setup.description')}
            </p>
          )}
        </div>
        {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
      </div>

      <nav aria-label={t('setup.navigation')} className="flex flex-wrap gap-1 border-b border-border">
        {tabs.map(({ id, label, count, icon: Icon }) => {
          const to = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/${id}`
          return (
            <Link key={id} to={to} aria-current={activeTab === id ? 'page' : undefined}
              onClick={(event) => followLink(event, to)}
              className={cn('flex items-center gap-2 border-b-2 px-3 sm:px-4 py-2 sm:py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                activeTab === id ? 'border-primary text-primary' : 'border-transparent text-muted-foreground hover:text-foreground')}>
              <Icon className="size-4" />{label}
              {count !== undefined && <Badge variant="secondary" className="min-w-5 justify-center px-1.5 text-xs">{count}</Badge>}
            </Link>
          )
        })}
      </nav>
      {children}
    </Page>
  )
}

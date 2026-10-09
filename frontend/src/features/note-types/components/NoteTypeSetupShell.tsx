import type { MouseEvent, ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Layers, List } from 'lucide-react'
import { AmbientBackground } from '@/components/ambient-background'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Page, PageHeader } from '@/shared/components/Page'
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
}

export function NoteTypeSetupShell({ noteTypeId, name, activeTab, fieldCount, templateCount, children, actions, onNavigate }: NoteTypeSetupShellProps) {
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
  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5">
      <AmbientBackground intensity="subtle" />
      <Button variant="ghost" size="sm" asChild className="-ml-2 text-muted-foreground gap-2">
        <Link to="/flashcards/note-types" onClick={(event) => followLink(event, '/flashcards/note-types')}>
          <ArrowLeft className="size-4" /> {t('setup.back')}
        </Link>
      </Button>
      <PageHeader title={name} description={t('setup.description')} actions={actions} />
      <nav aria-label={t('setup.navigation')} className="flex flex-wrap gap-1 border-b border-border">
        {tabs.map(({ id, label, count, icon: Icon }) => {
          const to = `/flashcards/note-types/${encodeURIComponent(noteTypeId)}/${id}`
          return (
            <Link key={id} to={to} aria-current={activeTab === id ? 'page' : undefined}
              onClick={(event) => followLink(event, to)}
              className={cn('flex items-center gap-2 border-b-2 px-3 sm:px-4 py-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
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

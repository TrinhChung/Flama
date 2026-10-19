import { Component, lazy, Suspense, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { DeckWorksheetModalProps } from './DeckWorksheetModal'

const WorksheetModal = lazy(() => import('./DeckWorksheetModal').then((module) => ({
  default: module.DeckWorksheetModal,
})))

function WorksheetLoadDialog({ onOpenChange, failed = false }: {
  onOpenChange: DeckWorksheetModalProps['onOpenChange']
  failed?: boolean
}) {
  const { t } = useTranslation('common')
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('worksheet_loader.title')}</DialogTitle>
          <DialogDescription>
            {failed ? t('worksheet_loader.failed') : t('worksheet_loader.loading')}
          </DialogDescription>
        </DialogHeader>
        {!failed && (
          <div role="status" className="flex justify-center py-6">
            <LoaderCircle className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">{t('worksheet_loader.sr_loading')}</span>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

class WorksheetLoadBoundary extends Component<{
  children: ReactNode
  onOpenChange: DeckWorksheetModalProps['onOpenChange']
}, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed
      ? <WorksheetLoadDialog failed onOpenChange={this.props.onOpenChange} />
      : this.props.children
  }
}

export function LazyDeckWorksheetModal(props: DeckWorksheetModalProps) {
  if (!props.open) return null
  return (
    <WorksheetLoadBoundary onOpenChange={props.onOpenChange}>
      <Suspense fallback={<WorksheetLoadDialog onOpenChange={props.onOpenChange} />}>
        <WorksheetModal {...props} />
      </Suspense>
    </WorksheetLoadBoundary>
  )
}

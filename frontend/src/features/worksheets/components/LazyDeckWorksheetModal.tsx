import { Component, lazy, Suspense, type ReactNode } from 'react'
import { LoaderCircle } from 'lucide-react'
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
  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mẫu giấy luyện viết &amp; In ấn (A4)</DialogTitle>
          <DialogDescription>
            {failed ? 'Không thể tải công cụ tạo bài tập. Hãy tải lại trang để thử lại.' : 'Đang tải công cụ tạo bài tập…'}
          </DialogDescription>
        </DialogHeader>
        {!failed && (
          <div role="status" className="flex justify-center py-6">
            <LoaderCircle className="size-6 animate-spin text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Đang tải…</span>
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

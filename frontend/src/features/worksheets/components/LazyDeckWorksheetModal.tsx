import { Component, lazy, Suspense, type ReactNode } from 'react'
import type { DeckWorksheetModalProps } from './DeckWorksheetModal'
import { WorksheetStudioDialog, WorksheetStudioLoadState } from './WorksheetStudioDialog'

const WorksheetStudio = lazy(() => import('./WorksheetStudio').then((module) => ({
  default: module.WorksheetStudio,
})))

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
      ? <WorksheetStudioLoadState failed onOpenChange={this.props.onOpenChange} />
      : this.props.children
  }
}

/**
 * Code-split studio entry point. The dialog frame stays mounted while the
 * studio chunk and its translations load, so it never reopens mid-load.
 */
export function LazyDeckWorksheetModal(props: DeckWorksheetModalProps) {
  if (!props.open) return null
  return (
    <WorksheetStudioDialog open onOpenChange={props.onOpenChange}>
      <WorksheetLoadBoundary onOpenChange={props.onOpenChange}>
        <Suspense fallback={<WorksheetStudioLoadState onOpenChange={props.onOpenChange} />}>
          <WorksheetStudio {...props} />
        </Suspense>
      </WorksheetLoadBoundary>
    </WorksheetStudioDialog>
  )
}

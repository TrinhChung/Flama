import { Component, type ReactNode } from 'react'
import { TranslationLoadError } from './loadGuard'

// Recovery copy cannot depend on the bundles whose download just failed.
export function TranslationLoadFailure() {
  return (
    <div role="alert" className="flex min-h-80 flex-col items-center justify-center gap-4 px-6 text-center">
      <p>Không tải được bản dịch. Vui lòng kiểm tra kết nối.<br />Translations could not load. Please check your connection.</p>
      <button type="button" className="rounded-md bg-primary px-4 py-2 text-primary-foreground" onClick={() => window.location.reload()}>
        Thử lại / Retry
      </button>
    </div>
  )
}

export class TranslationLoadBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) { return { error } }

  render() {
    if (this.state.error instanceof TranslationLoadError) return <TranslationLoadFailure />
    if (this.state.error) throw this.state.error
    return this.props.children
  }
}

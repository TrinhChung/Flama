import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ArrowLeft,
  FileQuestion,
  Home,
  Layers,
  RotateCw,
  ShieldAlert,
  ShoppingBag,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ApiError } from '@/shared/api/client'

type StudyScopeErrorCardProps = {
  error: unknown
  deckName?: string | null
  deckId?: string | null
  onRetry?: () => void
}

type ErrorDetails = {
  deck_id?: number | string
  deck_name?: string
  marketplace_url?: string
  marketplace_item_id?: string
}

export function StudyScopeErrorCard({
  error,
  deckName,
  deckId,
  onRetry,
}: StudyScopeErrorCardProps) {
  const isApiError = error instanceof ApiError
  const errorCode = isApiError ? error.code : ''
  const errorStatus = isApiError ? error.status : 0
  const details = (isApiError && error.details && typeof error.details === 'object'
    ? error.details as ErrorDetails
    : {})

  const isAccessDenied = errorCode === 'DECK_ACCESS_DENIED' || errorStatus === 403
  const isDeckNotFound = errorCode === 'DECK_NOT_FOUND' || (
    errorStatus === 404 && errorCode !== 'NO_STUDY_CARDS' && errorCode !== 'NOTE_TYPE_NOT_FOUND'
  )
  const isNoCards = errorCode === 'NO_STUDY_CARDS'
  const marketplaceUrl = details.marketplace_url || '/marketplace/decks'

  if (isAccessDenied) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-2xl border border-amber-200/80 dark:border-amber-900/50 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
          <div className="inline-flex items-center justify-center size-12 rounded-xl bg-amber-500/10 border border-amber-200 dark:border-amber-900/50 text-amber-600 dark:text-amber-400 mx-auto">
            <ShieldAlert className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {details.deck_name || deckName || (deckId ? `Deck #${deckId}` : 'Phiên học')}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              Bạn không thể truy cập bộ thẻ này
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Bộ thẻ này thuộc quyền sở hữu của người dùng khác hoặc chưa được cài đặt vào tài khoản của bạn.
              Hãy kiểm tra trên Chợ bộ thẻ để cài đặt hoặc quay lại trang chính.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to={marketplaceUrl}>
                <ShoppingBag className="mr-2 size-4" />
                Khám phá Chợ bộ thẻ
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                Về Dashboard
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (isDeckNotFound) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-2xl border border-border/80 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
          <div className="inline-flex items-center justify-center size-12 rounded-xl bg-muted border border-border text-muted-foreground mx-auto">
            <FileQuestion className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {deckId ? `Deck #${deckId}` : 'Phiên học'}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              Bộ thẻ không tồn tại
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Bộ thẻ này không tồn tại hoặc đã bị xóa. Vui lòng quay lại Dashboard để chọn bộ thẻ đang được cài đặt.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                Về Dashboard
              </Link>
            </Button>
            <Button asChild variant="outline" className="w-full sm:w-auto">
              <Link to="/marketplace/decks">
                <ShoppingBag className="mr-2 size-4" />
                Khám phá Chợ bộ thẻ
              </Link>
            </Button>
          </div>
        </div>
      </div>
    )
  }

  if (isNoCards) {
    return (
      <div className="w-full max-w-xl mx-auto py-6 px-4">
        <div className="rounded-2xl border border-border/80 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
          <div className="inline-flex items-center justify-center size-12 rounded-xl bg-muted border border-border text-muted-foreground mx-auto">
            <Layers className="size-6" />
          </div>

          <div className="space-y-2">
            <div className="text-xs font-medium text-muted-foreground">
              {deckName || (deckId ? `Deck #${deckId}` : 'Phiên học')}
            </div>
            <h2 className="text-2xl font-bold text-foreground tracking-tight">
              Bộ thẻ chưa có thẻ học
            </h2>
            <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
              Bộ thẻ này hiện chưa có thẻ nào để bắt đầu phiên ôn tập.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <Button asChild className="w-full sm:w-auto">
              <Link to="/dashboard">
                <Home className="mr-2 size-4" />
                Về Dashboard
              </Link>
            </Button>
            {deckId ? (
              <Button asChild variant="outline" className="w-full sm:w-auto">
                <Link to={`/browse?deck_id=${deckId}`}>
                  Quản lý thẻ
                </Link>
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    )
  }

  // Generic fallback error
  const errorMessage = error instanceof Error
    ? error.message
    : (typeof error === 'string' ? error : 'Đã có lỗi xảy ra khi tải phiên học.')

  return (
    <div className="w-full max-w-xl mx-auto py-6 px-4">
      <div className="rounded-2xl border border-destructive/30 bg-card p-6 sm:p-8 space-y-6 text-center shadow-xs">
        <div className="inline-flex items-center justify-center size-12 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive mx-auto">
          <AlertCircle className="size-6" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || (deckId ? `Deck #${deckId}` : 'Phiên học')}
          </div>
          <h2 className="text-2xl font-bold text-foreground tracking-tight">
            Không thể tải phiên học
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            {errorMessage}
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          {onRetry ? (
            <Button type="button" onClick={onRetry} className="w-full sm:w-auto">
              <RotateCw className="mr-2 size-4" />
              Thử lại
            </Button>
          ) : null}
          <Button asChild variant="outline" className="w-full sm:w-auto">
            <Link to="/dashboard">
              <ArrowLeft className="mr-2 size-4" />
              Về Dashboard
            </Link>
          </Button>
        </div>
      </div>
    </div>
  )
}

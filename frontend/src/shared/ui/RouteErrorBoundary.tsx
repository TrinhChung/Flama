import { useState } from 'react'
import { useRouteError, useNavigate, isRouteErrorResponse } from 'react-router-dom'
import { AlertTriangle, RotateCcw, Home, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function RouteErrorBoundary() {
  const error = useRouteError()
  const navigate = useNavigate()
  const [showDetails, setShowDetails] = useState(false)

  let errorMessage = 'Đã xảy ra sự cố không mong muốn trong ứng dụng.'
  let errorDetails = ''

  if (isRouteErrorResponse(error)) {
    errorMessage = `${error.status} ${error.statusText}`
    errorDetails = typeof error.data === 'string' ? error.data : JSON.stringify(error.data, null, 2)
  } else if (error instanceof Error) {
    errorMessage = error.message
    errorDetails = error.stack || error.message
  } else if (typeof error === 'string') {
    errorMessage = error
  } else if (error != null) {
    errorDetails = JSON.stringify(error, null, 2)
  }

  return (
    <div className="flex min-h-[70svh] items-center justify-center p-4 sm:p-6 text-center">
      <div className="w-full max-w-md rounded-2xl border border-border/80 bg-card p-6 sm:p-8 shadow-sm space-y-5">
        <div className="mx-auto size-14 rounded-full bg-destructive/10 text-destructive flex items-center justify-center">
          <AlertTriangle className="size-7" />
        </div>

        <div className="space-y-2">
          <h2 className="text-lg sm:text-xl font-bold text-foreground">
            Đã xảy ra lỗi hiển thị
          </h2>
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
            Hệ thống gặp sự cố khi xử lý dữ liệu của màn hình này. Bạn có thể tải lại trang hoặc quay về trang chủ.
          </p>
        </div>

        {errorDetails && (
          <div className="text-left">
            <button
              type="button"
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mx-auto font-medium transition-colors"
            >
              <span>{showDetails ? 'Ẩn chi tiết kỹ thuật' : 'Xem chi tiết kỹ thuật'}</span>
              {showDetails ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>

            {showDetails && (
              <pre className="mt-2 p-3 rounded-lg bg-muted/60 border border-border text-[11px] font-mono text-destructive overflow-x-auto max-h-48 whitespace-pre-wrap break-words text-left">
                {errorMessage}
                {errorDetails && errorDetails !== errorMessage ? `\n\n${errorDetails}` : ''}
              </pre>
            )}
          </div>
        )}

        <div className="flex flex-col sm:flex-row items-center justify-center gap-2.5 pt-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.location.reload()}
            className="w-full sm:w-auto gap-2"
          >
            <RotateCcw className="size-3.5" />
            <span>Tải lại trang</span>
          </Button>
          <Button
            size="sm"
            onClick={() => navigate('/')}
            className="w-full sm:w-auto gap-2"
          >
            <Home className="size-3.5" />
            <span>Về trang chủ</span>
          </Button>
        </div>
      </div>
    </div>
  )
}

import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { LoaderCircle } from 'lucide-react'
import { useBootstrap } from '../../../shared/api/bootstrap'

export function RequireAuth() {
  const { data, isPending } = useBootstrap()
  const location = useLocation()

  if (isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
        <span className="sr-only">Đang kiểm tra phiên đăng nhập</span>
      </div>
    )
  }

  if (!data?.user) {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  return <Outlet />
}

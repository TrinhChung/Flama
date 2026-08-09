import { LoaderCircle } from 'lucide-react'
import { Navigate, Outlet } from 'react-router-dom'
import { useBootstrap } from '../../../shared/api/bootstrap'

export function RequireCreator() {
  const { data, isPending } = useBootstrap()

  if (isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
        <span className="sr-only">Đang kiểm tra quyền Nhà sáng tạo</span>
      </div>
    )
  }

  const hasCreatorAccess =
    data?.user?.is_admin || data?.user?.role?.code === 'creator'

  return hasCreatorAccess ? <Outlet /> : <Navigate to="/dashboard" replace />
}

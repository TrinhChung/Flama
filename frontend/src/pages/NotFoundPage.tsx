import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60svh] items-center justify-center px-4 py-20 text-center">
      <div className="max-w-lg space-y-5">
        <p className="text-7xl font-black tracking-tight text-primary">404</p>
        <h1 className="text-2xl font-bold">Không tìm thấy trang</h1>
        <p className="text-muted-foreground">
          Route này chưa tồn tại trong frontend React hoặc đã được di chuyển.
        </p>
        <Button asChild>
          <Link to="/">
            <ArrowLeft />
            Về trang chính
          </Link>
        </Button>
      </div>
    </div>
  )
}

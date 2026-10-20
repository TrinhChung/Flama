import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Brand } from '@/shared/components/Brand'
import { StoryControls } from './StoryControls'

type StoryPreviewShellProps = {
  signedIn: boolean
  motionEnabled: boolean
  onToggleMotion: () => void
  children: ReactNode
}

/** Header and footer for the review route, separate from the app's PublicLayout. */
export function StoryPreviewShell({
  signedIn,
  motionEnabled,
  onToggleMotion,
  children,
}: StoryPreviewShellProps) {
  return (
    <>
      <div className="bg-[#2a211d] px-5 py-2 text-center text-sm text-[#fff8ef] sm:px-10">
        <span className="whitespace-nowrap font-semibold">Bản xem trước landing mới</span>
        <span aria-hidden="true" className="mx-2 opacity-60">
          ·
        </span>
        <Link to="/" className="whitespace-nowrap underline underline-offset-4 hover:text-[#fea00e]">
          Về trang hiện tại
        </Link>
      </div>
      <header className="story-header sticky top-0 z-30 border-b border-border/60 bg-background/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between gap-3 px-4 sm:px-10 lg:px-16">
          <Brand compact />
          <div className="flex items-center gap-2">
            <StoryControls motionEnabled={motionEnabled} onToggleMotion={onToggleMotion} />
            {signedIn ? (
              <Button asChild className="h-11 rounded-full px-4 text-sm">
                <Link to="/dashboard">Vào Flama</Link>
              </Button>
            ) : (
              <Button asChild variant="ghost" className="h-11 rounded-full px-4 text-sm">
                <Link to="/login">Đăng nhập</Link>
              </Button>
            )}
          </div>
        </div>
      </header>

      {children}

      <footer className="border-t border-border bg-background">
        <div className="mx-auto flex max-w-[1280px] flex-col gap-4 px-5 py-8 text-sm text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-10 lg:px-16">
          <p>© {new Date().getFullYear()} Flama · Cùng học, cùng chia sẻ</p>
          <nav aria-label="Liên kết hỗ trợ và pháp lý" className="flex flex-wrap gap-x-5 gap-y-2">
            <Link className="inline-flex min-h-11 items-center hover:text-foreground" to="/support">
              Hỗ trợ
            </Link>
            <Link className="inline-flex min-h-11 items-center hover:text-foreground" to="/terms">
              Điều khoản
            </Link>
            <Link className="inline-flex min-h-11 items-center hover:text-foreground" to="/privacy">
              Bảo mật
            </Link>
          </nav>
        </div>
      </footer>
    </>
  )
}

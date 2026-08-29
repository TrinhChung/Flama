import { useEffect } from 'react'
import {
  BookOpen,
  Goal,
  Heart,
  HelpCircle,
  LoaderCircle,
  LogIn,
  LogOut,
  Menu,
  Store,
  UserPlus,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { AmbientBackground } from '@/components/ambient-background'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteFooter } from '@/components/site-footer'
import { SiteMascot } from '@/components/site-mascot'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Separator } from '@/components/ui/separator'
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from '@/components/ui/sidebar'
import { appApi } from '@/app/api'
import { bootstrapQueryKey, useBootstrap } from '@/shared/api/bootstrap'
import { Brand } from '@/shared/components/Brand'
import type { FrontendBootstrap } from '@/shared/types/api'

const pageTitles: Record<string, string> = {
  '/dashboard': 'Tổng quan',
  '/statistics': 'Thống kê',
  '/browse': 'Duyệt thẻ',
  '/study': 'Học flashcard',
  '/note-types': 'Loại thẻ',
  '/installed-decks': 'Deck đã cài',
  '/audio/generate': 'Studio tạo âm thanh Deck',
  '/audio': 'Studio tạo âm thanh Deck',
  '/import': 'Import thẻ',
  '/sync': 'Đồng bộ Anki Desktop',
  '/marketplace/decks': 'Bộ thẻ',
  '/marketplace/decks/publish': 'Đăng bộ thẻ',
  '/marketplace/note-types': 'Loại thẻ',
  '/marketplace/note-types/publish': 'Đăng loại thẻ',
  '/orders': 'Đơn hàng',
  '/profile': 'Trang cá nhân & Ví',
  '/settings/goals': 'Mục tiêu học tập',
  '/settings/mcp-tokens': 'MCP Tokens',
  '/settings/yomitan': 'Kết nối Yomitan',
  '/guide': 'Trung tâm Trợ giúp',
  '/guide/flama-audio': 'Tải Flama Audio',
  '/feedback': 'Đóng góp ý kiến',
  '/tickets': 'Báo lỗi & Góp ý',
  '/support/feedback': 'Đóng góp ý kiến',
  '/admin/users': 'Quản lý người dùng',
  '/admin/permissions': 'Phân quyền người dùng',
  '/admin/payments': 'Quản lý thanh toán',
  '/admin/tts': 'TTS Provider',
  '/admin/image-library': 'Thư viện ảnh Admin',
  '/admin/tickets': 'Quản lý Ticket & Báo lỗi',
  '/admin/support': 'Cấu hình Ủng hộ Admin',
}

function PublicLayout({
  bootstrap,
  onLogout,
}: {
  bootstrap: FrontendBootstrap
  onLogout?: () => void
}) {
  const location = useLocation()
  const isLogin = location.pathname.startsWith('/login')
  const isSupport = location.pathname.startsWith('/support')
  const user = bootstrap.user

  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden">
      <AmbientBackground intensity="vibrant" />
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 shadow-xs backdrop-blur-md transition-all">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 md:px-6">
          <Brand compact />

          <nav className="hidden items-center gap-2.5 sm:flex">
            <Link
              to="/support"
              className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all ${
                isSupport
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
              }`}
            >
              <Heart className="size-3.5 fill-rose-500/20 text-rose-500" />
              Ủng hộ
            </Link>

            {!user ? (
              <>
                <Link
                  to="/login"
                  className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-xs font-semibold transition-all ${
                    isLogin
                      ? 'bg-muted text-foreground'
                      : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                  }`}
                >
                  <LogIn className="size-3.5" />
                  Đăng nhập
                </Link>

                <Link
                  to="/register"
                  className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 px-5 py-2 text-xs font-bold text-primary-foreground shadow-sm shadow-primary/25 transition-all hover:opacity-95 hover:shadow-md hover:shadow-primary/30"
                >
                  <UserPlus className="size-3.5" />
                  Đăng ký ngay
                </Link>
              </>
            ) : (
              <>
                <Link
                  to="/dashboard"
                  className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 px-4 py-2 text-xs font-bold text-primary-foreground shadow-sm shadow-primary/25 transition-all hover:opacity-95 hover:shadow-md hover:shadow-primary/30"
                >
                  <BookOpen className="size-3.5" />
                  Vào Dashboard
                </Link>

                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="flex items-center gap-2 rounded-full border border-border/60 bg-muted/40 p-1 pr-1.5 pl-2.5 text-xs font-semibold transition hover:bg-muted/80"
                    >
                      <span className="max-w-[120px] truncate text-foreground">
                        {user.username}
                      </span>
                      {user.is_admin ? (
                        <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                          Admin
                        </span>
                      ) : null}
                      <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 font-bold text-primary">
                        {user.username[0]?.toUpperCase() || 'U'}
                      </span>
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-52 space-y-1 p-1.5">
                    <div className="mb-1 border-b px-2 py-1.5">
                      <p className="truncate text-xs font-bold text-foreground">
                        {user.username}
                      </p>
                      <p className="truncate text-[11px] text-muted-foreground">
                        {user.email}
                      </p>
                    </div>
                    <DropdownMenuItem asChild>
                      <Link to="/dashboard" className="flex items-center gap-2">
                        <BookOpen className="size-4" />
                        <span>Tổng quan</span>
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/orders" className="flex items-center gap-2">
                        <Heart className="size-4 text-rose-500" />
                        <span>Đơn hàng</span>
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/guide" className="flex items-center gap-2">
                        <HelpCircle className="size-4 text-primary" />
                        <span>Trợ giúp</span>
                      </Link>
                    </DropdownMenuItem>
                    {onLogout && (
                      <DropdownMenuItem
                        className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                        onSelect={onLogout}
                      >
                        <LogOut className="size-4" />
                        <span>Đăng xuất</span>
                      </DropdownMenuItem>
                    )}
                  </DropdownMenuContent>
                </DropdownMenu>
              </>
            )}
          </nav>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                className="sm:hidden"
                variant="outline"
                size="icon"
                aria-label="Mở menu"
              >
                <Menu className="size-5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52 space-y-1 p-1.5">
              {user && (
                <div className="mb-1 border-b px-2 py-1.5">
                  <p className="truncate text-xs font-bold text-foreground">
                    {user.username}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {user.email}
                  </p>
                </div>
              )}
              {user && (
                <DropdownMenuItem asChild>
                  <Link to="/marketplace/decks" className="flex items-center gap-2">
                    <Store className="size-4" />
                    <span>Marketplace</span>
                  </Link>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem asChild>
                <Link to="/support" className="flex items-center gap-2">
                  <Heart className="size-4 text-rose-500" />
                  <span>Ủng hộ</span>
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/guide" className="flex items-center gap-2">
                  <HelpCircle className="size-4 text-primary" />
                  <span>Trợ giúp</span>
                </Link>
              </DropdownMenuItem>
              {!user ? (
                <>
                  <DropdownMenuItem asChild>
                    <Link to="/login" className="flex items-center gap-2">
                      <LogIn className="size-4" />
                      <span>Đăng nhập</span>
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link
                      to="/register"
                      className="flex items-center gap-2 font-semibold text-primary"
                    >
                      <UserPlus className="size-4" />
                      <span>Đăng ký</span>
                    </Link>
                  </DropdownMenuItem>
                </>
              ) : (
                <>
                  <DropdownMenuItem asChild>
                    <Link to="/dashboard" className="flex items-center gap-2 font-semibold text-primary">
                      <BookOpen className="size-4" />
                      <span>Vào Dashboard</span>
                    </Link>
                  </DropdownMenuItem>
                  {onLogout && (
                    <DropdownMenuItem
                      className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                      onSelect={onLogout}
                    >
                      <LogOut className="size-4" />
                      <span>Đăng xuất</span>
                    </DropdownMenuItem>
                  )}
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <SiteFooter bootstrap={bootstrap} />
      <SiteMascot />
    </div>
  )
}

export function AppLayout() {
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    bootstrap?.messages.forEach((item, index) => {
      const options = { id: `bootstrap-${index}-${item.message}` }
      if (item.category === 'danger') toast.error(item.message, options)
      else if (item.category === 'warning') toast.warning(item.message, options)
      else if (item.category === 'success') toast.success(item.message, options)
      else toast.info(item.message, options)
    })
  }, [bootstrap?.messages])

  const logoutMutation = useMutation({
    mutationFn: () => appApi.logout(),
    onSuccess: () => {
      queryClient.setQueryData<FrontendBootstrap>(
        bootstrapQueryKey,
        (current) =>
          current ? { ...current, user: null, messages: [] } : current,
      )
      toast.success('Đã đăng xuất.')
      navigate('/', { replace: true })
    },
    onError: (error: Error) => {
      toast.error('Không thể đăng xuất', { description: error.message })
    },
  })

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
        <span className="sr-only">Đang kết nối máy chủ</span>
      </div>
    )
  }

  if (bootstrapQuery.error || !bootstrap) {
    return (
      <div className="mx-auto flex min-h-svh max-w-lg items-center px-6 text-center text-sm text-destructive">
        {bootstrapQuery.error?.message || 'Không thể tải phiên đăng nhập.'}
      </div>
    )
  }

  const publicPaths = [
    '/',
    '/login',
    '/register',
    '/support',
    '/terms',
    '/privacy',
    '/cookies',
  ]
  const isPublicPage = publicPaths.includes(location.pathname)

  if (!bootstrap.user || isPublicPage) {
    return (
      <PublicLayout
        bootstrap={bootstrap}
        onLogout={() => logoutMutation.mutate()}
      />
    )
  }

  if (location.pathname === '/study' || location.pathname === '/browse') {
    return (
      <main className="h-screen h-[100dvh] w-full overflow-hidden bg-background text-foreground">
        <Outlet />
      </main>
    )
  }

  const title = pageTitles[location.pathname] || 'Flama'

  return (
    <SidebarProvider>
      <AppSidebar
        bootstrap={bootstrap}
        onLogout={() => logoutMutation.mutate()}
        logoutPending={logoutMutation.isPending}
      />
      <SidebarInset className="relative min-w-0 overflow-hidden">
        <AmbientBackground intensity="normal" />
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border/50 bg-background/80 px-4 shadow-xs backdrop-blur-md md:px-6">
          <div className="flex items-center gap-2.5">
            <SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
            <Separator orientation="vertical" className="h-4" />
            <span className="truncate text-sm font-semibold text-foreground">
              {title}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1.5 sm:gap-2 rounded-full border border-border/60 bg-muted/40 p-1 pr-1.5 pl-2 text-xs font-semibold transition hover:bg-muted/80"
                >
                  <span className="max-w-[70px] sm:max-w-[120px] truncate text-foreground font-semibold">
                    {bootstrap.user.username}
                  </span>
                  {bootstrap.user.is_admin ? (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                      Admin
                    </span>
                  ) : null}
                  <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 font-bold text-primary">
                    {bootstrap.user.username[0]?.toUpperCase() || 'U'}
                  </span>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52 space-y-1 p-1.5">
                <div className="mb-1 border-b px-2 py-1.5">
                  <p className="truncate text-xs font-bold text-foreground">
                    {bootstrap.user.username}
                  </p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {bootstrap.user.email}
                  </p>
                </div>
                <DropdownMenuItem asChild>
                  <Link to="/dashboard" className="flex items-center gap-2">
                    <BookOpen className="size-4" />
                    <span>Tổng quan</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/settings/goals" className="flex items-center gap-2">
                    <Goal className="size-4" />
                    <span>Mục tiêu học tập</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/orders" className="flex items-center gap-2">
                    <Heart className="size-4 text-rose-500" />
                    <span>Đơn hàng</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/guide" className="flex items-center gap-2">
                    <HelpCircle className="size-4 text-primary" />
                    <span>Trợ giúp</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                  onSelect={() => logoutMutation.mutate()}
                >
                  <LogOut className="size-4" />
                  <span>Đăng xuất</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="min-h-[calc(100svh-3.5rem)] flex-1">
          <Outlet />
        </main>
        <SiteFooter bootstrap={bootstrap} />
        <SiteMascot />
      </SidebarInset>
    </SidebarProvider>
  )
}

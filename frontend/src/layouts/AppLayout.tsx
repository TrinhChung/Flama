import { useEffect } from 'react'
import {
  BookOpen,
  Check,
  Goal,
  Heart,
  HelpCircle,
  Languages,
  LogIn,
  LogOut,
  Menu,
  Store,
  UserPlus,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { AmbientBackground } from '@/components/ambient-background'
import { AppSidebar } from '@/components/app-sidebar'
import { SiteFooter } from '@/components/site-footer'
import { SiteMascot } from '@/components/site-mascot'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
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
import { LanguageSwitcher } from '@/shared/ui/LanguageSwitcher'
import type { FrontendBootstrap } from '@/shared/types/api'

const pageTitleKeyMap: Record<string, string> = {
  '/dashboard': 'page_titles.dashboard',
  '/statistics': 'page_titles.statistics',
  '/browse': 'page_titles.browse',
  '/study': 'page_titles.study',
  '/note-types': 'page_titles.note_types',
  '/card-templates': 'page_titles.card_templates',
  '/installed-decks': 'page_titles.installed_decks',
  '/audio/generate': 'page_titles.audio_generate',
  '/audio': 'page_titles.audio_generate',
  '/import': 'page_titles.import',
  '/sync': 'page_titles.sync',
  '/marketplace/decks': 'page_titles.marketplace_decks',
  '/marketplace/decks/publish': 'page_titles.marketplace_decks_publish',
  '/marketplace/note-types': 'page_titles.marketplace_note_types',
  '/marketplace/note-types/publish': 'page_titles.marketplace_note_types_publish',
  '/marketplace/templates': 'page_titles.marketplace_templates',
  '/orders': 'page_titles.orders',
  '/profile': 'page_titles.profile',
  '/settings/goals': 'page_titles.settings_goals',
  '/settings/mcp-tokens': 'page_titles.settings_mcp',
  '/settings/yomitan': 'page_titles.settings_yomitan',
  '/settings/asbplayer': 'page_titles.settings_asbplayer',
  '/guide': 'page_titles.guide',
  '/guide/flama-audio': 'page_titles.guide_flama_audio',
  '/feedback': 'page_titles.feedback',
  '/tickets': 'page_titles.tickets',
  '/support/feedback': 'page_titles.feedback',
  '/admin/users': 'page_titles.admin_users',
  '/admin/permissions': 'page_titles.admin_permissions',
  '/admin/mcp-tokens': 'page_titles.admin_mcp',
  '/admin/payments': 'page_titles.admin_payments',
  '/admin/tts': 'page_titles.admin_tts',
  '/admin/image-library': 'page_titles.admin_image_lib',
  '/admin/tickets': 'page_titles.admin_tickets',
  '/admin/support': 'page_titles.admin_support',
}

function PublicLayout({
  bootstrap,
  onLogout,
}: {
  bootstrap: FrontendBootstrap
  onLogout?: () => void
}) {
  const { t, i18n } = useTranslation('shell')
  const location = useLocation()
  const isLogin = location.pathname.startsWith('/login')
  const isSupport = location.pathname.startsWith('/support')
  const user = bootstrap.user
  const currentLang = (i18n.resolvedLanguage || i18n.language || 'vi').startsWith('en') ? 'en' : 'vi'

  return (
    <div className="relative flex min-h-svh flex-col overflow-hidden">
      <AmbientBackground intensity="vibrant" />
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/80 shadow-xs backdrop-blur-md transition-all">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 md:px-6">
          <Brand compact />

          <div className="hidden items-center gap-3 sm:flex">
            <nav className="flex items-center gap-2.5">
              <Link
                to="/support"
                className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-all ${
                  isSupport
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                }`}
              >
                <Heart className="size-3.5 fill-rose-500/20 text-rose-500" />
                {t('header.nav.support')}
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
                    {t('header.nav.login')}
                  </Link>

                  <Link
                    to="/register"
                    className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 px-5 py-2 text-xs font-bold text-primary-foreground shadow-sm shadow-primary/25 transition-all hover:opacity-95 hover:shadow-md hover:shadow-primary/30"
                  >
                    <UserPlus className="size-3.5" />
                    {t('header.nav.register')}
                  </Link>
                </>
              ) : (
                <>
                  <Link
                    to="/dashboard"
                    className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 px-4 py-2 text-xs font-bold text-primary-foreground shadow-sm shadow-primary/25 transition-all hover:opacity-95 hover:shadow-md hover:shadow-primary/30"
                  >
                    <BookOpen className="size-3.5" />
                    {t('header.nav.dashboard')}
                  </Link>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button
                        type="button"
                        className="flex items-center gap-2 rounded-full border border-border/60 bg-muted/40 p-1 pr-1.5 pl-2.5 text-xs font-semibold transition hover:bg-muted/80 cursor-pointer"
                      >
                        <span className="max-w-[120px] truncate text-foreground">
                          {user.username}
                        </span>
                        {user.is_admin ? (
                          <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                            {t('user_menu.admin_badge')}
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
                          <span>{t('user_menu.overview')}</span>
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/orders" className="flex items-center gap-2">
                          <Heart className="size-4 text-rose-500" />
                          <span>{t('user_menu.orders')}</span>
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuItem asChild>
                        <Link to="/guide" className="flex items-center gap-2">
                          <HelpCircle className="size-4 text-primary" />
                          <span>{t('user_menu.help')}</span>
                        </Link>
                      </DropdownMenuItem>
                      <DropdownMenuSub>
                        <DropdownMenuSubTrigger className="flex items-center gap-2 cursor-pointer">
                          <Languages className="size-4 text-muted-foreground" />
                          <span>{t('user_menu.language', 'Ngôn ngữ')}</span>
                          <span className="ml-auto text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                            {currentLang}
                          </span>
                        </DropdownMenuSubTrigger>
                        <DropdownMenuSubContent className="w-40 p-1">
                          <DropdownMenuItem
                            onSelect={() => void i18n.changeLanguage('vi')}
                            className="flex items-center justify-between text-xs cursor-pointer"
                          >
                            <span className="flex items-center gap-2">
                              <span className="text-base leading-none">🇻🇳</span>
                              <span>Tiếng Việt</span>
                            </span>
                            {currentLang === 'vi' && <Check className="size-3.5 text-primary" />}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            onSelect={() => void i18n.changeLanguage('en')}
                            className="flex items-center justify-between text-xs cursor-pointer"
                          >
                            <span className="flex items-center gap-2">
                              <span className="text-base leading-none">🇬🇧</span>
                              <span>English</span>
                            </span>
                            {currentLang === 'en' && <Check className="size-3.5 text-primary" />}
                          </DropdownMenuItem>
                        </DropdownMenuSubContent>
                      </DropdownMenuSub>
                      {onLogout && (
                        <DropdownMenuItem
                          className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                          onSelect={onLogout}
                        >
                          <LogOut className="size-4" />
                          <span>{t('user_menu.logout')}</span>
                        </DropdownMenuItem>
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </>
              )}
            </nav>

            <Separator orientation="vertical" className="h-4 bg-border/60" />

            {/* Corner Utility: Language Switcher at the far right corner */}
            <LanguageSwitcher />
          </div>

          <div className="flex items-center gap-2 sm:hidden">
            <LanguageSwitcher compact />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  aria-label={t('header.mobile_menu_aria')}
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
                      <span>{t('header.mobile.marketplace')}</span>
                    </Link>
                  </DropdownMenuItem>
                )}
                <DropdownMenuItem asChild>
                  <Link to="/support" className="flex items-center gap-2">
                    <Heart className="size-4 text-rose-500" />
                    <span>{t('header.mobile.support')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/guide" className="flex items-center gap-2">
                    <HelpCircle className="size-4 text-primary" />
                    <span>{t('header.mobile.help')}</span>
                  </Link>
                </DropdownMenuItem>
                {!user ? (
                  <>
                    <DropdownMenuItem asChild>
                      <Link to="/login" className="flex items-center gap-2">
                        <LogIn className="size-4" />
                        <span>{t('header.mobile.login')}</span>
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link
                        to="/register"
                        className="flex items-center gap-2 font-semibold text-primary"
                      >
                        <UserPlus className="size-4" />
                        <span>{t('header.mobile.register')}</span>
                      </Link>
                    </DropdownMenuItem>
                  </>
                ) : (
                  <>
                    <DropdownMenuItem asChild>
                      <Link to="/dashboard" className="flex items-center gap-2 font-semibold text-primary">
                        <BookOpen className="size-4" />
                        <span>{t('header.mobile.dashboard')}</span>
                      </Link>
                    </DropdownMenuItem>
                    {onLogout && (
                      <DropdownMenuItem
                        className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                        onSelect={onLogout}
                      >
                        <LogOut className="size-4" />
                        <span>{t('header.mobile.logout')}</span>
                      </DropdownMenuItem>
                    )}
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
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
  const { t, i18n } = useTranslation('shell')
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  const currentLang = (i18n.resolvedLanguage || i18n.language || 'vi').startsWith('en') ? 'en' : 'vi'

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
      toast.success(t('status.logout_success'))
      navigate('/', { replace: true })
    },
    onError: (error: Error) => {
      toast.error(t('status.logout_failed'), { description: error.message })
    },
  })

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Spinner size="lg" aria-label={t('status.connecting_server')} />
      </div>
    )
  }

  if (bootstrapQuery.error || !bootstrap) {
    return (
      <div className="mx-auto flex min-h-svh max-w-lg items-center px-6 text-center text-sm text-destructive">
        {bootstrapQuery.error?.message || t('status.session_load_failed')}
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
    '/marketplace-guidelines',
    '/community-guidelines',
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
      <main className="h-screen h-[100dvh] w-full overflow-hidden text-foreground">
        <Outlet />
      </main>
    )
  }

  const titleKey = pageTitleKeyMap[location.pathname]
    ?? (location.pathname.startsWith('/card-templates/') ? 'page_titles.card_templates' : undefined)
    ?? (/^\/installed-decks\/[^/]+\/templates$/.test(location.pathname) ? 'page_titles.received_templates' : undefined)
  const title = titleKey ? t(titleKey as any) : 'Flama'

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

          <div className="flex items-center gap-2 sm:gap-2.5">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1.5 sm:gap-2 rounded-full border border-border/60 bg-muted/40 p-1 pr-1.5 pl-2 text-xs font-semibold transition hover:bg-muted/80 cursor-pointer"
                >
                  <span className="max-w-[70px] sm:max-w-[120px] truncate text-foreground font-semibold">
                    {bootstrap.user.username}
                  </span>
                  {bootstrap.user.is_admin ? (
                    <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600 dark:text-amber-400">
                      {t('user_menu.admin_badge')}
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
                    <span>{t('user_menu.overview')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/settings/goals" className="flex items-center gap-2">
                    <Goal className="size-4" />
                    <span>{t('user_menu.study_goals')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/orders" className="flex items-center gap-2">
                    <Heart className="size-4 text-rose-500" />
                    <span>{t('user_menu.orders')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/guide" className="flex items-center gap-2">
                    <HelpCircle className="size-4 text-primary" />
                    <span>{t('user_menu.help')}</span>
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger className="flex items-center gap-2 cursor-pointer">
                    <Languages className="size-4 text-muted-foreground" />
                    <span>{t('user_menu.language', 'Ngôn ngữ')}</span>
                    <span className="ml-auto text-[10px] font-bold tracking-wider text-muted-foreground uppercase">
                      {currentLang}
                    </span>
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="w-40 p-1">
                    <DropdownMenuItem
                      onSelect={() => void i18n.changeLanguage('vi')}
                      className="flex items-center justify-between text-xs cursor-pointer"
                    >
                      <span className="flex items-center gap-2">
                        <span className="text-base leading-none">🇻🇳</span>
                        <span>Tiếng Việt</span>
                      </span>
                      {currentLang === 'vi' && <Check className="size-3.5 text-primary" />}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => void i18n.changeLanguage('en')}
                      className="flex items-center justify-between text-xs cursor-pointer"
                    >
                      <span className="flex items-center gap-2">
                        <span className="text-base leading-none">🇬🇧</span>
                        <span>English</span>
                      </span>
                      {currentLang === 'en' && <Check className="size-3.5 text-primary" />}
                    </DropdownMenuItem>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                <DropdownMenuItem
                  className="flex cursor-pointer items-center gap-2 text-destructive focus:text-destructive"
                  onSelect={() => logoutMutation.mutate()}
                >
                  <LogOut className="size-4" />
                  <span>{t('user_menu.logout')}</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="hidden sm:flex sm:items-center sm:gap-2.5">
              <Separator orientation="vertical" className="h-4 bg-border/60" />

              {/* Corner Utility: Language Switcher at the far right corner */}
              <LanguageSwitcher />
            </div>
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

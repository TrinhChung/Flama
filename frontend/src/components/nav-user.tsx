import {
  Check,
  ChevronsUpDown,
  CreditCard,
  Goal,
  HelpCircle,
  Key,
  Languages,
  LogOut,
  NotebookTabs,
  User as UserIcon,
  Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'
import type { FrontendLinks, FrontendUser } from '@/shared/types/api'

export function NavUser({
  user,
  links,
  onLogout,
  logoutPending,
}: {
  user: FrontendUser
  links: FrontendLinks
  onLogout: () => void
  logoutPending: boolean
}) {
  const { t, i18n } = useTranslation('shell')
  const { isMobile } = useSidebar()
  const currentLang = (i18n.resolvedLanguage || i18n.language || 'vi').startsWith('en') ? 'en' : 'vi'
  const displayName = user.display_name || user.username
  const initials = displayName.slice(0, 2).toUpperCase()
  const roleLabel = user.is_admin ? t('user_menu.role_admin') : user.role?.name || t('user_menu.role_user')

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="size-8 rounded-lg">
                {user.avatar_url ? (
                  <AvatarImage
                    src={user.avatar_url}
                    alt={displayName}
                    className="rounded-lg object-cover"
                  />
                ) : null}
                <AvatarFallback className="rounded-lg bg-primary/10 font-bold text-primary">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{displayName}</span>
                <span className="truncate text-xs text-muted-foreground">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-64"
            side={isMobile ? 'bottom' : 'right'}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel>
              <div className="flex items-center justify-between gap-2">
                <div className="truncate">
                  <p className="font-medium truncate">{displayName}</p>
                  <p className="text-xs font-normal text-muted-foreground truncate">
                    {roleLabel}
                  </p>
                </div>
                {user.balance_amount_display ? (
                  <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
                    {user.balance_amount_display}
                  </span>
                ) : null}
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem asChild>
                <Link to="/profile">
                  <UserIcon />
                  {t('user_menu.profile')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/settings/goals">
                  <Goal />
                  {t('user_menu.study_goals')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/wallet">
                  <Wallet />
                  {t('user_menu.wallet')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={links.orders}>
                  <CreditCard />
                  {t('user_menu.orders')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={links.note_types}>
                  <NotebookTabs />
                  {t('user_menu.manage_note_types')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/settings/mcp-tokens">
                  <Key />
                  {t('user_menu.mcp_ai')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/guide">
                  <HelpCircle />
                  {t('user_menu.help')}
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSub>
                <DropdownMenuSubTrigger className="cursor-pointer">
                  <Languages className="size-4" />
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
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              disabled={logoutPending}
              onSelect={onLogout}
            >
              <LogOut />
              {logoutPending ? t('user_menu.logging_out') : t('user_menu.logout')}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

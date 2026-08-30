import {
  ChevronsUpDown,
  CreditCard,
  Goal,
  HelpCircle,
  Key,
  LogOut,
  NotebookTabs,
  User as UserIcon,
  Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
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
  const { isMobile } = useSidebar()
  const displayName = user.display_name || user.username
  const initials = displayName.slice(0, 2).toUpperCase()

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
                    {user.is_admin ? 'Quản trị viên' : user.role?.name || 'Người dùng'}
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
                  Trang cá nhân
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/settings/goals">
                  <Goal />
                  Mục tiêu học tập
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/wallet">
                  <Wallet />
                  Ví & Doanh thu
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={links.orders}>
                  <CreditCard />
                  Lịch sử đơn hàng
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={links.note_types}>
                  <NotebookTabs />
                  Quản lý loại thẻ
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/settings/mcp-tokens">
                  <Key />
                  Kết nối AI (MCP)
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to="/guide">
                  <HelpCircle />
                  Trợ giúp
                </Link>
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem
              variant="destructive"
              disabled={logoutPending}
              onSelect={onLogout}
            >
              <LogOut />
              {logoutPending ? 'Đang đăng xuất…' : 'Đăng xuất'}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

import { ChevronsUpDown, CreditCard, Key, LogOut, NotebookTabs } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
  const initials = user.username.slice(0, 2).toUpperCase()

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
                <AvatarFallback className="rounded-lg bg-primary/10 text-primary">
                  {initials}
                </AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{user.username}</span>
                <span className="truncate text-xs text-muted-foreground">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="min-w-60"
            side={isMobile ? 'bottom' : 'right'}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel>
              <p className="font-medium">{user.username}</p>
              <p className="text-xs font-normal text-muted-foreground">
                {user.is_admin ? 'Quản trị viên' : user.role?.name || 'Người dùng'}
              </p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
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

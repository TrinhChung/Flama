import {
  AudioLines,
  ChartNoAxesColumn,
  CreditCard,
  GraduationCap,
  LayoutDashboard,
  NotebookTabs,
  PackageCheck,
  Search,
  Shapes,
  Store,
  Users,
} from 'lucide-react'
import { NavMain, type AppNavigationItem } from '@/components/nav-main'
import { NavUser } from '@/components/nav-user'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from '@/components/ui/sidebar'
import { Brand } from '@/shared/components/Brand'
import type { FrontendBootstrap } from '@/shared/types/api'

export function AppSidebar({
  bootstrap,
  onLogout,
  logoutPending,
  ...props
}: React.ComponentProps<typeof Sidebar> & {
  bootstrap: FrontendBootstrap
  onLogout: () => void
  logoutPending: boolean
}) {
  const primary: AppNavigationItem[] = [
    { title: 'Tổng quan', url: '/dashboard', icon: LayoutDashboard },
    { title: 'Thống kê', url: '/statistics', icon: ChartNoAxesColumn },
    { title: 'Duyệt thẻ', url: bootstrap.links.browse, icon: Search },
    { title: 'Học flashcard', url: bootstrap.links.study, icon: GraduationCap },
  ]
  const library: AppNavigationItem[] = [
    { title: 'Loại thẻ', url: bootstrap.links.note_types, icon: NotebookTabs },
    { title: 'Deck đã cài', url: bootstrap.links.installed_decks, icon: PackageCheck },
    { title: 'Kho shared deck', url: bootstrap.links.shared_decks, icon: Store },
    { title: 'Kho note type', url: bootstrap.links.shared_note_types, icon: Shapes },
  ]
  const admin: AppNavigationItem[] = [
    ...(bootstrap.links.admin_users
      ? [{ title: 'Người dùng', url: bootstrap.links.admin_users, icon: Users }]
      : []),
    ...(bootstrap.links.admin_payments
      ? [{ title: 'Thanh toán', url: bootstrap.links.admin_payments, icon: CreditCard }]
      : []),
    ...(bootstrap.links.admin_tts
      ? [{ title: 'TTS Provider', url: bootstrap.links.admin_tts, icon: AudioLines }]
      : []),
  ]

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="h-14 justify-center border-b">
        <Brand compact className="px-2 group-data-[collapsible=icon]:justify-center" />
      </SidebarHeader>
      <SidebarContent>
        <NavMain label="Học tập" items={primary} />
        <NavMain label="Học liệu" items={library} />
        {bootstrap.user?.is_admin ? <NavMain label="Quản trị" items={admin} /> : null}
      </SidebarContent>
      {bootstrap.user ? (
        <SidebarFooter>
          <NavUser
            user={bootstrap.user}
            links={bootstrap.links}
            onLogout={onLogout}
            logoutPending={logoutPending}
          />
        </SidebarFooter>
      ) : null}
      <SidebarRail />
    </Sidebar>
  )
}

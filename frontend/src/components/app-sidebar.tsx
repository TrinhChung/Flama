import {
  AudioLines,
  Bot,
  ChartNoAxesColumn,
  CreditCard,
  Download,
  Heart,
  Image as ImageIcon,
  Key,
  Layers,
  LayoutDashboard,
  MessageSquareHeart,
  NotebookTabs,
  PackageCheck,
  Search,
  Shapes,
  ShieldUser,
  Store,
  Ticket,
  TrendingUp,
  Upload,
  Users,
  Zap,
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
  ]
  const library: AppNavigationItem[] = [
    { title: 'Loại thẻ', url: bootstrap.links.note_types, icon: NotebookTabs },
    { title: 'Deck đã cài', url: bootstrap.links.installed_decks, icon: PackageCheck },
    { title: 'Kho shared deck', url: bootstrap.links.shared_decks, icon: Store },
    { title: 'Kho note type', url: bootstrap.links.shared_note_types, icon: Shapes },
    { title: 'Đăng học liệu', url: '/marketplace/decks/publish', icon: Upload },
  ]

  const extensions: AppNavigationItem[] = [
    { title: 'Tạo âm thanh Deck', url: '/audio/generate', icon: AudioLines },
    { title: 'Tải Flama Audio', url: '/guide/flama-audio', icon: Download },
    { title: 'Kết nối Yomitan', url: '/settings/yomitan', icon: Key },
    { title: 'Kết nối AI (MCP)', url: '/settings/mcp-tokens', icon: Bot },
  ]

  const creator: AppNavigationItem[] = [
    { title: 'Đồng bộ Anki Desktop', url: '/sync', icon: Zap },
    { title: 'Nhập file (CSV/TSV)', url: '/import', icon: Upload },
  ]

  const admin: AppNavigationItem[] = [
    { title: 'Tăng trưởng & Thống kê', url: '/admin/analytics', icon: TrendingUp },
    ...(bootstrap.links.admin_users
      ? [
          { title: 'Người dùng', url: bootstrap.links.admin_users, icon: Users },
          { title: 'Phân quyền', url: '/admin/permissions', icon: ShieldUser },
        ]
      : []),
    ...(bootstrap.links.admin_payments
      ? [{ title: 'Thanh toán', url: bootstrap.links.admin_payments, icon: CreditCard }]
      : []),
    ...(bootstrap.links.admin_tts
      ? [{ title: 'TTS Provider', url: bootstrap.links.admin_tts, icon: AudioLines }]
      : []),
    { title: 'Thư viện ảnh', url: '/admin/image-library', icon: ImageIcon },
    { title: 'Phân loại & Metadata', url: '/admin/taxonomy', icon: Layers },
    { title: 'Quản lý Ticket', url: '/admin/tickets', icon: Ticket },
    { title: 'Cấu hình Ủng hộ', url: '/admin/support', icon: Heart },
  ]

  const settings: AppNavigationItem[] = [
    { title: 'Đóng góp ý kiến', url: '/feedback', icon: MessageSquareHeart },
  ]

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="h-14 justify-center border-b px-2 group-data-[collapsible=icon]:px-0">
        <Brand compact hideTextOnCollapse className="px-2 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:justify-center" />
      </SidebarHeader>
      <SidebarContent>
        <NavMain label="Học tập" items={primary} />
        <NavMain label="Học liệu" items={library} />
        <NavMain label="Nhập & Đồng bộ" items={creator} />
        <NavMain label="Phần mở rộng" items={extensions} />
        {bootstrap.user?.is_admin ? <NavMain label="Quản trị Admin" items={admin} /> : null}
        <NavMain label="Cài đặt" items={settings} />
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

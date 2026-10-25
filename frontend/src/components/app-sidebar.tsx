import {
  AudioLines,
  BadgePercent,
  BookOpenCheck,
  Bot,
  ChartNoAxesColumn,
  CreditCard,
  Download,
  Gauge,
  Headphones,
  Heart,
  HelpCircle,
  ImageIcon,
  KeyRound,
  Layers,
  LayoutDashboard,
  MessageSquareHeart,
  NotebookTabs,
  Palette,
  PackageCheck,
  Printer,
  Search,
  Shapes,
  ShieldUser,
  Store,
  Ticket,
  TrendingUp,
  Upload,
  User,
  Users,
  Wallet,
  Zap,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
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
  const { t } = useTranslation('shell')

  const primary: AppNavigationItem[] = [
    { title: t('sidebar.item.overview'), url: '/dashboard', icon: LayoutDashboard },
    { title: t('sidebar.item.statistics'), url: '/statistics', icon: ChartNoAxesColumn },
    { title: t('sidebar.item.browse'), url: bootstrap.links.browse, icon: Search },
    { title: t('sidebar.item.worksheets'), url: '/worksheets', icon: Printer },
  ]
  const library: AppNavigationItem[] = [
    // Nhóm Học liệu cá nhân / Quản trị
    { title: t('sidebar.item.installed_decks'), url: bootstrap.links.installed_decks, icon: PackageCheck },
    { title: t('sidebar.item.note_types'), url: bootstrap.links.note_types, icon: NotebookTabs },
    { title: t('sidebar.item.card_templates'), url: '/card-templates', icon: Layers },
    // Nhóm Chợ / Chia sẻ cộng đồng
    { title: t('sidebar.item.shared_decks'), url: bootstrap.links.shared_decks, icon: Store },
    { title: t('sidebar.item.shared_note_types'), url: bootstrap.links.shared_note_types, icon: Shapes },
    { title: t('sidebar.item.shared_templates'), url: '/marketplace/templates', icon: Palette },
    { title: t('sidebar.item.publish_deck'), url: '/marketplace/decks/publish', icon: Upload },
    { title: t('sidebar.item.publish_note_type'), url: '/marketplace/note-types/publish', icon: Shapes },
  ]

  const extensions: AppNavigationItem[] = [
    { title: t('sidebar.item.deck_audio'), url: '/audio/generate', icon: AudioLines },
    { title: t('sidebar.item.flama_audio'), url: '/guide/flama-audio', icon: Download },
    { title: t('sidebar.item.yomitan'), url: '/settings/yomitan', icon: BookOpenCheck },
    { title: t('sidebar.item.asbplayer'), url: '/settings/asbplayer', icon: Headphones },
    { title: t('sidebar.item.mcp_ai'), url: '/settings/mcp-tokens', icon: Bot },
  ]

  const creator: AppNavigationItem[] = [
    { title: t('sidebar.item.anki_sync'), url: '/sync', icon: Zap },
    { title: t('sidebar.item.file_import'), url: '/import', icon: Upload },
  ]

  const admin: AppNavigationItem[] = [
    { title: t('sidebar.item.admin_analytics'), url: '/admin/analytics', icon: TrendingUp },
    ...(bootstrap.links.admin_users
      ? [
          { title: t('sidebar.item.admin_users'), url: bootstrap.links.admin_users, icon: Users },
          { title: t('sidebar.item.admin_permissions'), url: '/admin/permissions', icon: ShieldUser },
        ]
      : []),
    ...(bootstrap.links.admin_mcp_tokens
      ? [{ title: t('sidebar.item.admin_mcp'), url: bootstrap.links.admin_mcp_tokens, icon: KeyRound }]
      : []),
    ...(bootstrap.links.admin_payments
      ? [
          { title: t('sidebar.item.admin_payments'), url: bootstrap.links.admin_payments, icon: CreditCard },
          { title: t('sidebar.item.admin_fees'), url: '/admin/fees', icon: BadgePercent },
        ]
      : [{ title: t('sidebar.item.admin_fees'), url: '/admin/fees', icon: BadgePercent }]),
    { title: t('sidebar.item.admin_quotas'), url: '/admin/quotas', icon: Gauge },
    ...(bootstrap.links.admin_tts
      ? [{ title: t('sidebar.item.admin_tts'), url: bootstrap.links.admin_tts, icon: AudioLines }]
      : []),
    { title: t('sidebar.item.admin_images'), url: '/admin/image-library', icon: ImageIcon },
    { title: t('sidebar.item.admin_taxonomy'), url: '/admin/taxonomy', icon: Layers },
    { title: t('sidebar.item.admin_tickets'), url: '/admin/tickets', icon: Ticket },
    { title: t('sidebar.item.admin_support'), url: '/admin/support', icon: Heart },
  ]

  const settings: AppNavigationItem[] = [
    { title: t('sidebar.item.profile'), url: '/profile', icon: User },
    { title: t('sidebar.item.wallet'), url: '/wallet', icon: Wallet },
    { title: t('sidebar.item.orders'), url: '/orders', icon: CreditCard },
    { title: t('sidebar.item.help'), url: '/guide', icon: HelpCircle },
    { title: t('sidebar.item.feedback'), url: '/feedback', icon: MessageSquareHeart },
  ]

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="h-14 justify-center border-b px-2 group-data-[collapsible=icon]:px-0">
        <Brand compact hideTextOnCollapse className="px-2 group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:justify-center" />
      </SidebarHeader>
      <SidebarContent>
        <NavMain label={t('sidebar.group.learning')} items={primary} />
        <NavMain label={t('sidebar.group.materials')} items={library} />
        <NavMain label={t('sidebar.group.import_sync')} items={creator} />
        <NavMain label={t('sidebar.group.extensions')} items={extensions} />
        {bootstrap.user?.is_admin ? <NavMain label={t('sidebar.group.admin')} items={admin} /> : null}
        <NavMain label={t('sidebar.group.settings')} items={settings} />
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

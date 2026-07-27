import type { LucideIcon } from 'lucide-react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from '@/components/ui/sidebar'

export type AppNavigationItem = {
  title: string
  url: string
  icon: LucideIcon
  external?: boolean
}

export function NavMain({
  label,
  items,
}: {
  label: string
  items: AppNavigationItem[]
}) {
  const location = useLocation()
  const { isMobile, setOpenMobile } = useSidebar()
  if (!items.length) return null
  const closeMobile = () => {
    if (isMobile) setOpenMobile(false)
  }

  return (
    <SidebarGroup>
      <SidebarGroupLabel>{label}</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={`${item.title}-${item.url}`}>
            {item.external ? (
              <SidebarMenuButton asChild tooltip={item.title}>
                <a href={item.url} onClick={closeMobile}>
                  <item.icon />
                  <span>{item.title}</span>
                </a>
              </SidebarMenuButton>
            ) : (
              <SidebarMenuButton
                asChild
                isActive={location.pathname === item.url}
                tooltip={item.title}
              >
                <NavLink to={item.url} onClick={closeMobile}>
                  <item.icon />
                  <span>{item.title}</span>
                </NavLink>
              </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  )
}

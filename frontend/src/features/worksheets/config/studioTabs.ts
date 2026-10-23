import { Database, FileText, LayoutGrid, Sliders } from 'lucide-react'
import type { ParseKeys } from 'i18next'
import type { TemplateIcon } from './templateIcons'

export type StudioTab = 'template' | 'data' | 'layout' | 'header'

export interface StudioTabConfig {
  id: StudioTab
  labelKey: ParseKeys<'worksheets'>
  label: string
  shortLabel: string
  icon: TemplateIcon
}

export const STUDIO_TABS: StudioTabConfig[] = [
  { id: 'template', labelKey: 'studio.tabs.template', label: 'Mẫu bài tập', shortLabel: 'Mẫu', icon: LayoutGrid },
  { id: 'data', labelKey: 'studio.tabs.data', label: 'Dữ liệu & Trường', shortLabel: 'Dữ liệu', icon: Database },
  { id: 'layout', labelKey: 'studio.tabs.layout', label: 'Bố cục & Ô chữ', shortLabel: 'Bố cục', icon: Sliders },
  { id: 'header', labelKey: 'studio.tabs.header', label: 'Tiêu đề & Thông tin', shortLabel: 'Tiêu đề', icon: FileText },
]

export function nextStudioTab(current: StudioTab): StudioTab {
  const index = STUDIO_TABS.findIndex((tab) => tab.id === current)
  return STUDIO_TABS[(index + 1) % STUDIO_TABS.length].id
}

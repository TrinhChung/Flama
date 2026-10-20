import { Database, FolderTree, LayoutGrid, Printer } from 'lucide-react'
import type { ParseKeys } from 'i18next'
import type { TemplateIcon } from './templateIcons'

export type WizardStepId = 'deck' | 'mapping' | 'template' | 'studio'

export interface WizardStepConfig {
  id: WizardStepId
  number: number
  labelKey: ParseKeys<'worksheets'>
  label: string
  shortLabelKey: ParseKeys<'worksheets'>
  shortLabel: string
  icon: TemplateIcon
}

export const WIZARD_STEPS: WizardStepConfig[] = [
  {
    id: 'deck',
    number: 1,
    labelKey: 'stepper.step_deck',
    label: 'Chọn bộ thẻ',
    shortLabelKey: 'stepper.step_deck_short',
    shortLabel: 'Bộ thẻ',
    icon: FolderTree,
  },
  {
    id: 'mapping',
    number: 2,
    labelKey: 'stepper.step_mapping',
    label: 'Ánh xạ dữ liệu',
    shortLabelKey: 'stepper.step_mapping_short',
    shortLabel: 'Ánh xạ',
    icon: Database,
  },
  {
    id: 'template',
    number: 3,
    labelKey: 'stepper.step_template',
    label: 'Chọn mẫu bài tập',
    shortLabelKey: 'stepper.step_template_short',
    shortLabel: 'Mẫu bài',
    icon: LayoutGrid,
  },
  {
    id: 'studio',
    number: 4,
    labelKey: 'stepper.step_studio',
    label: 'Cấu hình & In ấn',
    shortLabelKey: 'stepper.step_studio_short',
    shortLabel: 'In ấn',
    icon: Printer,
  },
]

import type { MappingField } from '@/entities/card-template'

export type TemplateApplicationsPanelProps = {
  noteTypeId: string
  fields?: MappingField[]
  onChanged?: () => void
}

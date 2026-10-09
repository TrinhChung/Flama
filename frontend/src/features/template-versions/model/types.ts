import type { CardTemplateItem, TemplateVersionDetail, TemplateVersionList } from '@/entities/card-template'

export type TemplateVersionSource = {
  listKey: readonly unknown[]
  detailKey: (versionId: string) => readonly unknown[]
  list: (signal?: AbortSignal) => Promise<TemplateVersionList>
  get: (versionId: string, signal?: AbortSignal) => Promise<TemplateVersionDetail>
  restore: (versionId: string) => Promise<CardTemplateItem>
}

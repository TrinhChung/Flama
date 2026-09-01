export interface GuideStep {
  title: string
  description: string
  tip?: string
  badge?: string
}

export interface GuideShortcut {
  key: string
  action: string
  description: string
}

export interface GuideParam {
  name: string
  type?: string
  defaultValue?: string
  description: string
}

export interface GuideTroubleshootItem {
  symptom: string
  cause: string
  solution: string[]
}

export interface GuideArticle {
  slug: string
  title: string
  shortDescription: string
  categorySlug: string
  readTimeMinutes?: number
  updatedAt?: string
  intro?: string
  steps?: GuideStep[]
  shortcuts?: GuideShortcut[]
  params?: GuideParam[]
  troubleshoot?: GuideTroubleshootItem[]
  keyTakeaways?: string[]
  relatedArticleSlugs?: string[]
  troubleshootingSlug?: string
  detailedSections?: Array<{
    title: string
    content: string
    subitems?: string[]
  }>
}

export interface GuideCategory {
  slug: string
  title: string
  description: string
  iconName: string
  badge?: string
  articles: GuideArticle[]
}

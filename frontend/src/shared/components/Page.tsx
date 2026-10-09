import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const PAGE_SIZE_CLASSES = {
  /** Reading and form pages. */
  default: 'max-w-7xl',
  /** Lists and dashboards that benefit from extra columns on large screens. */
  wide: 'max-w-[120rem]',
  /** Editors and workspaces that should use the whole content area. */
  full: 'max-w-none',
} as const

export type PageSize = keyof typeof PAGE_SIZE_CLASSES

/**
 * Desktop pages that host a workspace fill the viewport below the 3.5rem app
 * header, so their last child can take the remaining height with `flex-1`.
 * Short screens keep a usable minimum (`--page-fill-min`, 48rem by default;
 * pages with taller headers raise it) and scroll the page instead.
 */
const PAGE_FILL_CLASS = 'lg:flex lg:h-[max(calc(100svh-3.5rem),var(--page-fill-min,48rem))] lg:flex-col'

export function Page({
  children,
  className,
  size = 'default',
  fill = false,
}: {
  children: ReactNode
  className?: string
  size?: PageSize
  fill?: boolean
}) {
  return (
    <div className={cn('mx-auto w-full space-y-6 px-4 py-6 md:px-6 md:py-8', PAGE_SIZE_CLASSES[size], fill && PAGE_FILL_CLASS, className)}>
      {children}
    </div>
  )
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight md:text-3xl">{title}</h1>
        {description ? (
          <p className="max-w-3xl text-sm text-muted-foreground md:text-base">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}

export function SectionCard({
  title,
  description,
  actions,
  children,
  className,
  contentClassName,
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  contentClassName?: string
}) {
  return (
    <Card className={className}>
      {title || description || actions ? (
        <CardHeader className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
          <div className="space-y-1">
            {title ? <CardTitle>{title}</CardTitle> : null}
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </CardHeader>
      ) : null}
      <CardContent className={cn(!title && !description && !actions && 'pt-6', contentClassName)}>
        {children}
      </CardContent>
    </Card>
  )
}

export function StatCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'default' | 'primary' | 'success' | 'warning'
}) {
  const toneClass = {
    default: 'bg-muted/35',
    primary: 'bg-primary/8 text-primary',
    success: 'bg-emerald-500/10 text-emerald-700',
    warning: 'bg-amber-500/10 text-amber-700',
  }[tone]

  return (
    <Card className="shadow-none">
      <CardContent className="p-4">
        <div className={cn('mb-3 inline-flex rounded-lg px-2 py-1 text-xs font-medium', toneClass)}>
          {label}
        </div>
        <div className="text-2xl font-bold tracking-tight">{value}</div>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </CardContent>
    </Card>
  )
}

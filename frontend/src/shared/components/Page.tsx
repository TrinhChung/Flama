import type { ReactNode } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

export function Page({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div className={cn('mx-auto w-full max-w-7xl space-y-6 px-4 py-6 md:px-6 md:py-8', className)}>
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
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            {title ? <CardTitle>{title}</CardTitle> : null}
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {actions}
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

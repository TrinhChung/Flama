import { Link } from 'react-router-dom'
import { cn } from '@/lib/utils'

export type BrandProps = {
  compact?: boolean
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  hideTextOnCollapse?: boolean
}

export function Brand({
  compact = false,
  size,
  className,
  hideTextOnCollapse = false,
}: BrandProps) {
  const resolvedSize = size || (compact ? 'sm' : 'md')

  const imgSizeClass = {
    sm: 'size-8',
    md: 'size-10',
    lg: 'size-14',
    xl: 'size-16',
  }[resolvedSize]

  const textSizeClass = {
    sm: 'text-lg',
    md: 'text-2xl',
    lg: 'text-3xl lg:text-4xl',
    xl: 'text-4xl lg:text-5xl',
  }[resolvedSize]

  return (
    <Link
      to="/"
      className={cn(
        'inline-flex items-center gap-3 font-semibold text-foreground transition-transform hover:scale-[1.02]',
        className,
      )}
    >
      <img
        src="/logo.png"
        alt=""
        aria-hidden="true"
        className={cn(imgSizeClass, 'shrink-0 object-contain drop-shadow-md')}
      />
      <span
        className={cn(
          'bg-gradient-to-r from-primary via-orange-500 to-amber-500 bg-clip-text font-black tracking-tight text-transparent drop-shadow-xs',
          textSizeClass,
          hideTextOnCollapse && 'group-data-[collapsible=icon]:hidden',
        )}
      >
        Flama
      </span>
    </Link>
  )
}

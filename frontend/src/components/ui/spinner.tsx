import * as React from 'react'
import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'default' | 'lg' | 'xl'
  iconClassName?: string
}

const sizeClasses = {
  sm: 'size-4',
  default: 'size-6',
  lg: 'size-8',
  xl: 'size-12',
}

export const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ className, size = 'default', iconClassName, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        className={cn('inline-flex items-center justify-center', className)}
        {...props}
      >
        <LoaderCircle
          className={cn('animate-spin text-primary', sizeClasses[size], iconClassName)}
          aria-hidden="true"
        />
        <span className="sr-only">Đang tải...</span>
      </div>
    )
  },
)

Spinner.displayName = 'Spinner'

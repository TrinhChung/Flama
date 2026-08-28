import {
  AlertTriangle,
  BookOpen,
  HelpCircle,
  LifeBuoy,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

export interface ContextHelpButtonProps {
  guidePath: string
  guideTitle?: string
  troubleshootPath?: string
  troubleshootTitle?: string
  label?: string
  tooltip?: string
  variant?: 'button' | 'icon' | 'outline' | 'subtle'
  size?: 'sm' | 'default' | 'xs'
  className?: string
}

export function ContextHelpButton({
  guidePath,
  guideTitle = 'Xem tài liệu hướng dẫn',
  troubleshootPath,
  troubleshootTitle = 'Khắc phục sự cố thường gặp',
  label = 'Trợ giúp',
  tooltip = 'Xem tài liệu hướng dẫn sử dụng',
  variant = 'outline',
  size = 'sm',
  className = '',
}: ContextHelpButtonProps) {
  // If there's no troubleshootPath, render a direct link or tooltip button
  if (!troubleshootPath) {
    if (variant === 'icon') {
      return (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                asChild
                variant="ghost"
                size="icon"
                className={`size-8 rounded-full text-muted-foreground hover:bg-primary/10 hover:text-primary transition-all ${className}`}
              >
                <Link to={guidePath} aria-label={tooltip}>
                  <HelpCircle className="size-4" />
                </Link>
              </Button>
            </TooltipTrigger>
            <TooltipContent side="bottom" className="text-xs font-medium">
              {tooltip}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )
    }

    return (
      <Button
        asChild
        variant={variant === 'subtle' ? 'secondary' : variant === 'outline' ? 'outline' : 'default'}
        size={size === 'xs' ? 'sm' : size}
        className={`gap-1.5 font-medium transition-all ${
          size === 'xs' ? 'h-7 text-xs px-2.5 rounded-lg' : 'rounded-xl'
        } ${className}`}
      >
        <Link to={guidePath}>
          <HelpCircle className="size-3.5" />
          <span>{label}</span>
        </Link>
      </Button>
    )
  }

  // If both guide and troubleshoot exist, render a stylish dropdown
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        {variant === 'icon' ? (
          <Button
            variant="ghost"
            size="icon"
            className={`size-8 rounded-full text-muted-foreground hover:bg-primary/10 hover:text-primary transition-all ${className}`}
            aria-label="Menu Trợ giúp"
          >
            <HelpCircle className="size-4" />
          </Button>
        ) : (
          <Button
            variant={variant === 'subtle' ? 'secondary' : variant === 'outline' ? 'outline' : 'default'}
            size={size === 'xs' ? 'sm' : size}
            className={`gap-1.5 font-medium transition-all ${
              size === 'xs' ? 'h-7 text-xs px-2.5 rounded-lg' : 'rounded-xl'
            } ${className}`}
          >
            <LifeBuoy className="size-3.5 text-primary" />
            <span>{label}</span>
          </Button>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64 p-1.5 rounded-xl shadow-lg border-border/80">
        <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-2 py-1">
          Hỗ trợ & Hướng dẫn
        </DropdownMenuLabel>
        <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-primary/10 focus:text-primary">
          <Link to={guidePath} className="flex items-start gap-2.5 w-full">
            <div className="size-6 rounded-md bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
              <BookOpen className="size-3.5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-foreground">{guideTitle}</div>
              <div className="text-[11px] text-muted-foreground line-clamp-1">Quy trình & mẹo học chuẩn</div>
            </div>
          </Link>
        </DropdownMenuItem>

        <DropdownMenuSeparator className="my-1" />

        <DropdownMenuItem asChild className="rounded-lg p-2 cursor-pointer focus:bg-amber-500/10 focus:text-amber-600 dark:focus:text-amber-400">
          <Link to={troubleshootPath} className="flex items-start gap-2.5 w-full">
            <div className="size-6 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0 mt-0.5">
              <AlertTriangle className="size-3.5" />
            </div>
            <div className="min-w-0">
              <div className="text-xs font-semibold text-foreground">{troubleshootTitle}</div>
              <div className="text-[11px] text-muted-foreground line-clamp-1">Khắc phục sự cố nhanh</div>
            </div>
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

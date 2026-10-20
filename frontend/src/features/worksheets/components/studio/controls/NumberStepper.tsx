import { Minus, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

const SIZES = {
  sm: { button: 'size-7.5 shrink-0', icon: 'size-3', input: 'h-7.5 text-xs text-center font-bold' },
  md: { button: 'size-8.5 shrink-0', icon: 'size-3.5', input: 'h-8.5 text-xs text-center font-bold' },
} as const

/** − [number] unit + control; callers own clamping and the fallback for unset values. */
export function NumberStepper({
  value,
  min,
  max,
  unit,
  size = 'md',
  className = 'flex items-center gap-1.5',
  onDecrement,
  onIncrement,
  onValueChange,
}: {
  value: number
  min: number
  max: number
  unit: string
  size?: keyof typeof SIZES
  className?: string
  onDecrement: () => void
  onIncrement: () => void
  /** Receives every parsable typed value. */
  onValueChange: (value: number) => void
}) {
  const classes = SIZES[size]
  return (
    <div className={className}>
      <Button type="button" variant="outline" size="icon" className={classes.button} onClick={onDecrement}>
        <Minus className={classes.icon} />
      </Button>
      <div className="flex-1 flex items-center gap-1">
        <Input
          type="number"
          min={min}
          max={max}
          value={value}
          onChange={(e) => {
            const val = parseInt(e.target.value, 10)
            if (!isNaN(val)) onValueChange(val)
          }}
          className={classes.input}
        />
        <span className="text-xs font-semibold text-muted-foreground">{unit}</span>
      </div>
      <Button type="button" variant="outline" size="icon" className={classes.button} onClick={onIncrement}>
        <Plus className={classes.icon} />
      </Button>
    </div>
  )
}

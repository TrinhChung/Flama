import { Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'

type StoryControlsProps = {
  motionEnabled: boolean
  onToggleMotion: () => void
}

export function StoryControls({ motionEnabled, onToggleMotion }: StoryControlsProps) {
  return (
    <Button
      type="button"
      variant="outline"
      className="h-11 min-w-11 rounded-full px-3 text-sm sm:px-4"
      onClick={onToggleMotion}
    >
      {motionEnabled ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
      <span className="sr-only sm:not-sr-only">{motionEnabled ? 'Tắt chuyển động' : 'Bật chuyển động'}</span>
    </Button>
  )
}

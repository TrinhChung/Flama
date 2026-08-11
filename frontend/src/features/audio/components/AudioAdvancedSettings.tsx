import type { Dispatch, SetStateAction } from 'react'

interface AudioAdvancedSettingsProps {
  volumeScale: number
  setVolumeScale: Dispatch<SetStateAction<number>>
  pitch: number
  setPitch: Dispatch<SetStateAction<number>>
  speed: number
  setSpeed: Dispatch<SetStateAction<number>>
  intonationScale: number
  setIntonationScale: Dispatch<SetStateAction<number>>
  isProcessing: boolean
}

export function AudioAdvancedSettings({
  volumeScale,
  setVolumeScale,
  pitch,
  setPitch,
  speed,
  setSpeed,
  intonationScale,
  setIntonationScale,
  isProcessing,
}: AudioAdvancedSettingsProps) {
  return (
    <div className="grid gap-3.5 sm:grid-cols-2 pt-1">
      {/* Volume Scale */}
      <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
        <div className="flex items-center justify-between text-xs font-medium text-foreground">
          <span>Âm lượng</span>
          <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
            {volumeScale.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="2"
          step="0.01"
          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          value={volumeScale}
          onChange={(e) => setVolumeScale(parseFloat(e.target.value))}
          disabled={isProcessing}
        />
      </div>

      {/* Pitch */}
      <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
        <div className="flex items-center justify-between text-xs font-medium text-foreground">
          <span>Cao độ</span>
          <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
            {pitch.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="-0.4"
          max="0.4"
          step="0.01"
          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          value={pitch}
          onChange={(e) => setPitch(parseFloat(e.target.value))}
          disabled={isProcessing}
        />
      </div>

      {/* Speed */}
      <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
        <div className="flex items-center justify-between text-xs font-medium text-foreground">
          <span>Tốc độ đọc</span>
          <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
            {speed.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0.1"
          max="4"
          step="0.01"
          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          value={speed}
          onChange={(e) => setSpeed(parseFloat(e.target.value))}
          disabled={isProcessing}
        />
      </div>

      {/* Intonation */}
      <div className="p-3.5 bg-background border border-border/60 rounded-xl space-y-2 hover:border-primary/40 transition-colors shadow-2xs">
        <div className="flex items-center justify-between text-xs font-medium text-foreground">
          <span>Ngữ điệu</span>
          <span className="font-mono text-[11px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-md">
            {intonationScale.toFixed(2)}
          </span>
        </div>
        <input
          type="range"
          min="0"
          max="2"
          step="0.01"
          className="w-full h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
          value={intonationScale}
          onChange={(e) => setIntonationScale(parseFloat(e.target.value))}
          disabled={isProcessing}
        />
      </div>
    </div>
  )
}

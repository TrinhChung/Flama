type AmbientBackgroundProps = {
  className?: string
  intensity?: 'normal' | 'subtle' | 'vibrant'
}

export function AmbientBackground({
  className = '',
  intensity = 'normal',
}: AmbientBackgroundProps) {
  const primaryGlowOpacity =
    intensity === 'vibrant' ? '22%' : intensity === 'subtle' ? '12%' : '18%'
  const secondaryGlowOpacity =
    intensity === 'vibrant' ? '14%' : intensity === 'subtle' ? '8%' : '10%'
  const gridMix =
    intensity === 'vibrant' ? '25%' : intensity === 'subtle' ? '16%' : '20%'

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 -z-10 overflow-hidden ${className}`}
    >
      {/* Ambient background glow */}
      <div
        className="pointer-events-none absolute inset-0 -z-20 transition-all duration-500"
        style={{
          background: `radial-gradient(circle at 25% 25%, color-mix(in oklab, var(--color-primary) ${primaryGlowOpacity}, transparent), transparent 55%), radial-gradient(circle at 75% 75%, color-mix(in oklab, var(--color-primary) ${secondaryGlowOpacity}, transparent), transparent 45%)`,
        }}
      />

      {/* Standard 36px Grid pattern with vignette mask */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_90%_80%_at_50%_50%,black_75%,transparent_100%)] transition-all duration-500"
        style={{
          backgroundImage: `linear-gradient(to right, color-mix(in oklab, var(--color-border) ${gridMix}, transparent) 1px, transparent 1px), linear-gradient(to bottom, color-mix(in oklab, var(--color-border) ${gridMix}, transparent) 1px, transparent 1px)`,
        }}
      />
    </div>
  )
}

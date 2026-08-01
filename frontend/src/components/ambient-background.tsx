type AmbientBackgroundProps = {
  className?: string
  intensity?: 'normal' | 'subtle' | 'vibrant'
}

export function AmbientBackground({
  className = '',
  intensity = 'normal',
}: AmbientBackgroundProps) {
  const primaryGlowOpacity =
    intensity === 'vibrant' ? '14%' : intensity === 'subtle' ? '8%' : '11%'
  const secondaryGlowOpacity =
    intensity === 'vibrant' ? '8%' : intensity === 'subtle' ? '5%' : '6%'
  const gridMix =
    intensity === 'vibrant' ? '35%' : intensity === 'subtle' ? '22%' : '28%'
  const circleMix =
    intensity === 'vibrant' ? '12%' : intensity === 'subtle' ? '6%' : '8%'

  return (
    <div
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 -z-10 overflow-hidden ${className}`}
    >
      {/* Ambient background glow (Pushed to bottom corners to keep top header clean and clear) */}
      <div
        className="pointer-events-none absolute inset-0 -z-20 transition-all duration-500"
        style={{
          background: `radial-gradient(circle at 20% 90%, color-mix(in oklab, var(--color-primary) ${primaryGlowOpacity}, transparent), transparent 55%), radial-gradient(circle at 80% 90%, color-mix(in oklab, var(--color-primary) ${secondaryGlowOpacity}, transparent), transparent 55%)`,
        }}
      />

      {/* Bold Grid Lines + Soft Concentric Circles */}
      <div
        className="pointer-events-none absolute inset-0 -z-10 bg-[size:36px_36px] [mask-image:radial-gradient(ellipse_90%_80%_at_50%_50%,black_85%,transparent_100%)] transition-all duration-500"
        style={{
          backgroundImage: `
            repeating-radial-gradient(
              circle at 50% 50%,
              color-mix(in oklab, var(--color-border) ${circleMix}, transparent) 0,
              color-mix(in oklab, var(--color-border) ${circleMix}, transparent) 1px,
              transparent 1px,
              transparent 48px
            ),
            linear-gradient(to right, color-mix(in oklab, var(--color-border) ${gridMix}, transparent) 1px, transparent 1px),
            linear-gradient(to bottom, color-mix(in oklab, var(--color-border) ${gridMix}, transparent) 1px, transparent 1px)
          `,
        }}
      />
    </div>
  )
}

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'flama:landing-story:motion'

function readStoredPreference(): boolean | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (value === 'on') return true
    if (value === 'off') return false
  } catch {
    // Storage can be unavailable (private mode, blocked site data).
  }
  return null
}

function useMediaQuery(query: string) {
  const [matches, setMatches] = useState(() =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches,
  )

  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setMatches(media.matches)
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [query])

  return matches
}

/**
 * Motion is on unless the system asks for reduced motion or the viewer turned it
 * off with the in-page toggle. The viewer's explicit choice wins over the system.
 */
export function useStoryMotionPreference() {
  const systemReduced = useMediaQuery('(prefers-reduced-motion: reduce)')
  const isWide = useMediaQuery('(min-width: 1024px)')
  const [override, setOverride] = useState<boolean | null>(readStoredPreference)

  const motionEnabled = override ?? !systemReduced

  const toggleMotion = useCallback(() => {
    const next = !motionEnabled
    setOverride(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? 'on' : 'off')
    } catch {
      // Keep the in-memory choice when storage is unavailable.
    }
  }, [motionEnabled])

  return { motionEnabled, isWide, toggleMotion }
}

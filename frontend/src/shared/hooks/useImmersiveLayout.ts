import { useLayoutEffect } from 'react'
import { useOutletContext } from 'react-router-dom'

export type AppLayoutContext = {
  setImmersive: (immersive: boolean) => void
}

export function useImmersiveLayout(immersive: boolean) {
  const context = useOutletContext<AppLayoutContext | null>()
  const setImmersive = context?.setImmersive

  useLayoutEffect(() => {
    setImmersive?.(immersive)
    return () => setImmersive?.(false)
  }, [immersive, setImmersive])
}

import { useEffect } from 'react'
import type { createBrowserRouter } from 'react-router-dom'
import { MAINTENANCE_PATH, subscribeBackendUnavailable } from '@/shared/api/backendAvailability'

export function useBackendAvailabilityRedirect(router: Pick<ReturnType<typeof createBrowserRouter>, 'state' | 'navigate'>) {
  useEffect(() => subscribeBackendUnavailable(() => {
    if (router.state.location.pathname !== MAINTENANCE_PATH) {
      void router.navigate(MAINTENANCE_PATH, { replace: true })
    }
  }), [router])
}

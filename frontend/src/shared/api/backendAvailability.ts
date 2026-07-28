export const MAINTENANCE_PATH = '/maintenance'

const RETURN_PATH_STORAGE_KEY = 'flama:maintenance:return-path'
const unavailableListeners = new Set<() => void>()
const unavailableStatuses = new Set([502, 503, 504, 521, 522, 523, 524])

let backendUnavailable = false

function isSafeReturnPath(value: string | null): value is string {
  return Boolean(
    value &&
      value.startsWith('/') &&
      !value.startsWith('//') &&
      !value.startsWith(MAINTENANCE_PATH),
  )
}

function rememberCurrentPath() {
  if (typeof window === 'undefined') return

  const currentPath = `${window.location.pathname}${window.location.search}${window.location.hash}`
  if (!isSafeReturnPath(currentPath)) return

  try {
    window.sessionStorage.setItem(RETURN_PATH_STORAGE_KEY, currentPath)
  } catch {
    // Session storage can be unavailable in privacy-restricted browsers.
  }
}

export function isBackendUnavailableStatus(status: number): boolean {
  return unavailableStatuses.has(status)
}

export function reportBackendUnavailable() {
  rememberCurrentPath()
  backendUnavailable = true
  unavailableListeners.forEach((listener) => listener())
}

export function subscribeBackendUnavailable(listener: () => void) {
  unavailableListeners.add(listener)
  if (backendUnavailable) listener()

  return () => {
    unavailableListeners.delete(listener)
  }
}

export function clearBackendUnavailable() {
  backendUnavailable = false
}

export function getMaintenanceReturnPath(): string {
  if (typeof window === 'undefined') return '/'

  try {
    const storedPath = window.sessionStorage.getItem(RETURN_PATH_STORAGE_KEY)
    if (isSafeReturnPath(storedPath)) return storedPath
  } catch {
    // Fall back to the landing page when storage cannot be read.
  }

  return '/'
}

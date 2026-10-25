import { useEffect, useRef } from 'react'

export function useBrowseTableScroll(page: number) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (typeof ref.current?.scrollTo === 'function') ref.current.scrollTo({ top: 0, behavior: 'instant' })
    else if (ref.current) ref.current.scrollTop = 0
  }, [page])
  return ref
}

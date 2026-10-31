import { useEffect, useState } from 'react'

type Listener = (entry: IntersectionObserverEntry) => void

// One observer per margin serves every element using that margin.
const sharedObservers = new Map<string, { observer: IntersectionObserver; listeners: Map<Element, Listener> }>()

function observerFor(margin: string) {
  let shared = sharedObservers.get(margin)
  if (!shared) {
    const listeners = new Map<Element, Listener>()
    const observer = new IntersectionObserver(
      (entries) => entries.forEach((entry) => listeners.get(entry.target)?.(entry)),
      { rootMargin: margin },
    )
    shared = { observer, listeners }
    sharedObservers.set(margin, shared)
  }
  return shared
}

/**
 * Whether an element is within `margin` of the viewport, for mounting long
 * lists only where the reader is. Also returns the element's last height
 * while it was near, so a placeholder can keep the same size.
 * Without IntersectionObserver (tests, old browsers) everything is near.
 * `initiallyNear` renders at once what is surely on screen, before the first
 * observation arrives.
 */
export function useNearViewport<T extends Element>(margin = '1200px 0px', initiallyNear = false) {
  const supported = typeof IntersectionObserver !== 'undefined'
  const [element, setElement] = useState<T | null>(null)
  const [near, setNear] = useState(!supported || initiallyNear)
  const [height, setHeight] = useState<number | null>(null)

  useEffect(() => {
    if (!element || !supported) return
    const { observer, listeners } = observerFor(margin)
    listeners.set(element, (entry) => {
      if (!entry.isIntersecting && entry.boundingClientRect.height > 0) {
        setHeight(entry.boundingClientRect.height)
      }
      setNear(entry.isIntersecting)
    })
    observer.observe(element)
    return () => {
      listeners.delete(element)
      observer.unobserve(element)
    }
  }, [element, margin, supported])

  return { ref: setElement, near, height }
}

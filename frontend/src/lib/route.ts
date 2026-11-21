import { useEffect, useState } from 'react'

/**
 * Pages live in the URL hash, so a reload, a bookmark or a second tab opens the same thing:
 *   #/new                              paste a new job
 *   #/applications/42                  application 42 (its sent version, else the newest)
 *   #/applications/42/versions/7       application 42 at CV version 7
 *   #/tracker   #/profile
 */
export type Route =
  | { page: 'new' }
  | { page: 'tracker' }
  | { page: 'profile' }
  | { page: 'application'; id: number; versionId: number | null }

const CHANGED = 'cv-tailor:route' // navigate(..., {replace}) changes the URL without a hashchange event

export function parse(hash: string): Route {
  const path = hash.replace(/^#\/?/, '').replace(/\/$/, '')
  if (path === 'tracker') return { page: 'tracker' }
  if (path === 'profile') return { page: 'profile' }
  const m = path.match(/^applications\/(\d+)(?:\/versions\/(\d+))?$/)
  if (m) return { page: 'application', id: Number(m[1]), versionId: m[2] ? Number(m[2]) : null }
  return { page: 'new' }
}

export function href(route: Route): string {
  if (route.page === 'application') {
    return `#/applications/${route.id}` + (route.versionId != null ? `/versions/${route.versionId}` : '')
  }
  return `#/${route.page}`
}

/** Go to a page. `replace`: update the URL without adding a back-button step (e.g. after saving a version). */
export function navigate(route: Route, { replace = false } = {}) {
  const target = href(route)
  if (window.location.hash === target) return
  if (replace) {
    window.history.replaceState(null, '', target)
    window.dispatchEvent(new Event(CHANGED))
  } else {
    window.location.hash = target
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parse(window.location.hash))
  useEffect(() => {
    const onChange = () => {
      const next = parse(window.location.hash)
      setRoute(prev => (href(prev) === href(next) ? prev : next))
    }
    window.addEventListener('hashchange', onChange)
    window.addEventListener(CHANGED, onChange)
    return () => {
      window.removeEventListener('hashchange', onChange)
      window.removeEventListener(CHANGED, onChange)
    }
  }, [])
  return route
}

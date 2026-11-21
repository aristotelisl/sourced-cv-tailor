import { useEffect, useState } from 'react'

export type Route = 'tailor' | 'tracker' | 'profile'

const HASHES: Record<Route, string> = { tailor: '#/', tracker: '#/tracker', profile: '#/profile' }

function current(): Route {
  return (Object.keys(HASHES) as Route[]).find(r => r !== 'tailor' && HASHES[r] === window.location.hash) ?? 'tailor'
}

export function href(route: Route): string {
  return HASHES[route]
}

/** A few pages, kept in the URL hash so a reload stays on the same page. */
export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(current)
  useEffect(() => {
    const onChange = () => setRoute(current())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function navigate(route: Route) {
  window.location.hash = HASHES[route]
}

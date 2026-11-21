import { useEffect, useState } from 'react'

export type Route = 'tailor' | 'tracker'

function current(): Route {
  return window.location.hash === '#/tracker' ? 'tracker' : 'tailor'
}

/** Two pages, kept in the URL hash so a reload stays on the same page. */
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
  window.location.hash = route === 'tracker' ? '#/tracker' : '#/'
}

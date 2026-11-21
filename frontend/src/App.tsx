import { AnalysisPanel } from '@/components/AnalysisPanel'
import { Editor } from '@/components/Editor'
import { Extras } from '@/components/Extras'
import { GapReport } from '@/components/GapReport'
import { HeaderExtras } from '@/components/HeaderExtras'
import { JobInput } from '@/components/JobInput'
import { Preview } from '@/components/Preview'
import { ProfilePage } from '@/components/ProfilePage'
import { Tracker } from '@/components/Tracker'
import { useEffect } from 'react'

import { href, navigate, type Route, useRoute } from '@/lib/route'
import { cn } from '@/lib/utils'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { useStore } from '@/store'

function ErrorAlert() {
  const { error, clearError } = useStore()
  if (!error) return null
  return (
    <Alert variant="destructive">
      <AlertTitle>{error.message}</AlertTitle>
      {error.problems.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-5">{error.problems.map(p => <li key={p}>{p}</li>)}</ul>
        </AlertDescription>
      )}
      <Button size="xs" variant="ghost" className="mt-2" onClick={clearError}>Dismiss</Button>
    </Alert>
  )
}

type Page = 'tailor' | 'tracker' | 'profile'

function NavLink({ to, page, current, children }: { to: Route; page: Page; current: Page; children: string }) {
  return (
    <a href={href(to)}
       className={cn('rounded-md px-2 py-1 text-sm', page === current ? 'bg-muted font-medium' : 'text-muted-foreground')}>
      {children}
    </a>
  )
}

/** Keep the store on the application the URL names: #/applications/42 loads it, #/new clears it. */
function useApplicationFromUrl(route: Route) {
  useEffect(() => {
    const s = useStore.getState()
    if (route.page === 'application') {
      if (s.applicationId === route.id && (route.versionId === null || route.versionId === s.versionId)) return
      void s.openApplication(route.id, route.versionId).then(ok => {
        if (!ok) navigate({ page: 'new' }, { replace: true }) // e.g. deleted: the error explains
      })
    } else if (route.page === 'new' && s.applicationId !== null) {
      s.startNew()
    }
  }, [route])
}

export default function App() {
  const { analysis, cv, applicationId, versionId, reset, busy, profile, sampleChosen, error, loadProfileStatus } =
    useStore()
  const route = useRoute()
  useEffect(() => { loadProfileStatus() }, [loadProfileStatus])
  useApplicationFromUrl(route)

  // New users set up their profile first, unless they chose to explore with the sample one.
  const needsSetup = profile !== null &&
    (profile.state === 'missing' || (profile.state === 'example' && !sampleChosen))
  const current: Page = route.page === 'tracker' || route.page === 'profile' ? route.page : 'tailor'
  // Until the store holds what the URL names, show "Opening…" rather than the previous application or version.
  const opening = route.page === 'application' &&
    (applicationId !== route.id || (route.versionId !== null && route.versionId !== versionId))
  const page: Page | 'loading' = (profile === null && !error) || opening ? 'loading' : needsSetup ? 'profile' : current
  const splitView = page === 'tailor' && analysis !== null
  // "Tailor" goes back to the application you have open, if any.
  const tailorRoute: Route = applicationId !== null ? { page: 'application', id: applicationId, versionId } : { page: 'new' }

  const newJob = () => {
    // Saved versions are in the tracker and unsaved edits stay as a draft of their application.
    reset()
    navigate({ page: 'new' })
  }

  return (
    // In the split view the page itself doesn't scroll on large screens: each column scrolls on its own.
    <div className={cn('min-h-screen bg-muted/40', splitView && 'lg:flex lg:h-screen lg:flex-col')}>
      <header className="flex items-center gap-3 border-b bg-background px-6 py-3">
        <h1 className="mr-4 text-base font-semibold">CV Tailor</h1>
        <NavLink to={tailorRoute} page="tailor" current={current}>Tailor</NavLink>
        <NavLink to={{ page: 'tracker' }} page="tracker" current={current}>Tracker</NavLink>
        <NavLink to={{ page: 'profile' }} page="profile" current={current}>Profile</NavLink>
        {(analysis || current === 'tracker') && page !== 'profile' && (
          <Button size="sm" variant="outline" className="ml-auto" onClick={newJob} disabled={busy !== null}>
            New application
          </Button>
        )}
      </header>

      {page === 'loading' ? (
        <main className="mx-auto max-w-3xl p-6 text-sm text-muted-foreground">
          {opening && busy === 'open' ? 'Opening the application…' : null}
        </main>
      ) : page === 'profile' ? (
        <main className="mx-auto max-w-3xl space-y-4 p-6">
          <ProfilePage />
        </main>
      ) : page === 'tracker' ? (
        <main className="mx-auto max-w-6xl space-y-4 p-6">
          <ErrorAlert />
          <Tracker />
        </main>
      ) : !analysis ? (
        <main className="mx-auto max-w-3xl space-y-4 p-6">
          <ErrorAlert />
          {profile?.state === 'example' && (
            <Alert>
              <AlertTitle>You're exploring with the sample profile</AlertTitle>
              <AlertDescription>
                CVs will use {profile.name}'s experience (a fictional person).{' '}
                <a href={href({ page: 'profile' })} className="font-medium underline">Set up your own profile</a> from your CV.
              </AlertDescription>
            </Alert>
          )}
          <JobInput />
        </main>
      ) : (
        <main className="mx-auto grid w-full max-w-[1700px] gap-6 p-6 lg:min-h-0 lg:flex-1 lg:grid-cols-2 lg:grid-rows-[minmax(0,1fr)] lg:py-0">
          <div className="min-w-0 space-y-4 lg:overflow-y-auto lg:py-6 lg:pr-2">
            <ErrorAlert />
            <AnalysisPanel />
            {cv && (
              <Card>
                <CardContent className="space-y-6">
                  <HeaderExtras />
                  <GapReport />
                </CardContent>
              </Card>
            )}
            {cv && (
              <Card>
                <CardContent><Editor /></CardContent>
              </Card>
            )}
            <Card>
              <CardContent><Extras /></CardContent>
            </Card>
          </div>
          <div className="min-w-0 lg:overflow-y-auto lg:py-6 lg:pr-2">
            <div>
              {cv ? <Preview /> : (
                <Card>
                  <CardContent className="py-16 text-center text-sm text-muted-foreground">
                    {busy === 'tailor'
                      ? 'Tailoring your CV… this takes about a minute.'
                      : 'Tailor the CV to see a live preview here.'}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </main>
      )}
    </div>
  )
}

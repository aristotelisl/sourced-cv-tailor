import { AnalysisPanel } from '@/components/AnalysisPanel'
import { Editor } from '@/components/Editor'
import { Extras } from '@/components/Extras'
import { GapReport } from '@/components/GapReport'
import { HeaderExtras } from '@/components/HeaderExtras'
import { JobInput } from '@/components/JobInput'
import { Preview } from '@/components/Preview'
import { Tracker } from '@/components/Tracker'
import { navigate, type Route, useRoute } from '@/lib/route'
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

function NavLink({ to, current, children }: { to: Route; current: Route; children: string }) {
  return (
    <a href={to === 'tracker' ? '#/tracker' : '#/'}
       className={cn('rounded-md px-2 py-1 text-sm', to === current ? 'bg-muted font-medium' : 'text-muted-foreground')}>
      {children}
    </a>
  )
}

export default function App() {
  const { analysis, cv, reset, busy } = useStore()
  const route = useRoute()
  const splitView = route !== 'tracker' && analysis !== null

  const newJob = () => {
    // Saved work is safe in the tracker; only unsaved edits would be lost.
    if (cv && !window.confirm('Start a new application? Unsaved edits to this CV will be lost (saved versions stay in the tracker).')) return
    reset()
    navigate('tailor')
  }

  return (
    // In the split view the page itself doesn't scroll on large screens: each column scrolls on its own.
    <div className={cn('min-h-screen bg-muted/40', splitView && 'lg:flex lg:h-screen lg:flex-col')}>
      <header className="flex items-center gap-3 border-b bg-background px-6 py-3">
        <h1 className="mr-4 text-base font-semibold">CV Tailor</h1>
        <NavLink to="tailor" current={route}>Tailor</NavLink>
        <NavLink to="tracker" current={route}>Tracker</NavLink>
        {(analysis || route === 'tracker') && (
          <Button size="sm" variant="outline" className="ml-auto" onClick={newJob} disabled={busy !== null}>
            New application
          </Button>
        )}
      </header>

      {route === 'tracker' ? (
        <main className="mx-auto max-w-6xl space-y-4 p-6">
          <ErrorAlert />
          <Tracker />
        </main>
      ) : !analysis ? (
        <main className="mx-auto max-w-3xl space-y-4 p-6">
          <ErrorAlert />
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

import { useCallback, useEffect, useState } from 'react'

import { ApiError, api, type ProfileView, type TailoredCV, type ViewEntry } from '@/api/client'
import { ProfileSetup } from '@/components/ProfileSetup'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useStore } from '@/store'

/** Every profile id the CV open in the app cites (bullet sources can be merged: "a+b"). */
function citedIds(cv: TailoredCV | null): string[] {
  if (!cv) return []
  return cv.sections.flatMap(s => s.entries.flatMap(e => [e.source, ...e.bullets.map(b => b.source)]))
    .flatMap(ref => ref.split('+'))
}

function Unverified() {
  return (
    <Badge variant="outline" className="border-amber-400 text-amber-800" title="verified: false in profile.yaml">
      unverified
    </Badge>
  )
}

function Added({ when }: { when: string | null }) {
  if (!when) return null
  return (
    <Badge variant="outline" className="border-emerald-400 text-emerald-800" title="From your answer to a gap-report question">
      {when} from an answer
    </Badge>
  )
}

function Entry({ entry }: { entry: ViewEntry }) {
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="font-medium">{entry.heading}</span>
        {entry.subheading && <span className="text-muted-foreground">{entry.subheading}</span>}
        {!entry.verified && <Unverified />}
        <Added when={entry.added} />
        {entry.dates && <span className="ml-auto text-xs text-muted-foreground">{entry.dates}</span>}
      </div>
      {entry.details.map(d => <div key={d} className="text-xs text-muted-foreground">{d}</div>)}
      {entry.items.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {entry.items.map(item => (
            <li key={item.id}>
              {item.text}{' '}
              {!item.verified && <Unverified />} <Added when={item.added} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function Section({ title, entries }: { title: string; entries: ViewEntry[] }) {
  if (!entries.length) return null
  return (
    <section className="space-y-3">
      <h3 className="border-b pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {entries.map(e => <Entry key={e.id} entry={e} />)}
    </section>
  )
}

function Skills({ skills }: { skills: ProfileView['skills'] }) {
  const groups: [string, string, string[]][] = [
    ['Strong', 'Used professionally or in a substantial project', skills.strong ?? []],
    ['Listed', 'On your CV, depth unknown', skills.listed ?? []],
    ['Never claimed', 'Never added to a CV, always reported as a gap', skills.not_claimed ?? []],
  ]
  return (
    <section className="space-y-2">
      <h3 className="border-b pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Skills</h3>
      {groups.filter(([, , items]) => items.length).map(([name, hint, items]) => (
        <div key={name} className="text-sm">
          <span className="font-medium" title={hint}>{name}:</span> {items.join(', ')}
        </div>
      ))}
    </section>
  )
}

type Mode = 'view' | 'edit' | 'import'

/** The Profile page: your profile as it is, editable as YAML, or replaced from a CV. */
export function ProfilePage() {
  const { profile, sampleChosen, cv, loadBank, loadProfileStatus } = useStore()
  const firstRun = profile === null || profile.state === 'missing' || (profile.state === 'example' && !sampleChosen)
  const [mode, setMode] = useState<Mode>('view')
  const [view, setView] = useState<ProfileView | null>(null)
  const [yaml, setYaml] = useState('')
  const [editBase, setEditBase] = useState('') // the profile the edit started from (the view may reload meanwhile)
  const [lost, setLost] = useState<string[]>([]) // ids the open CV uses that the edit removes
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)

  const load = useCallback(async () => {
    try {
      setView(await api.profileView())
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(String(e)))
    }
  }, [])
  useEffect(() => { if (!firstRun) void load() }, [firstRun, load, profile])

  if (firstRun) return <ProfileSetup />
  if (mode === 'import') return <ProfileSetup onCancel={() => setMode('view')} />

  const startEdit = () => {
    if (!view) return
    setYaml(view.yaml)
    setEditBase(view.base)
    setLost([])
    setError(null)
    setMode('edit')
  }

  const save = async (confirmed: boolean) => {
    if (!view) return
    setSaving(true)
    setError(null)
    try {
      if (!confirmed) {
        const check = await api.checkProfile(yaml, citedIds(cv))
        if (check.problems.length) throw new ApiError("That profile can't be saved", check.problems)
        if (check.missing_cited.length) {
          setLost(check.missing_cited)
          return
        }
      }
      await api.saveProfile(yaml, { base: editBase })
      setLost([])
      setMode('view')
      await Promise.all([load(), loadBank(true), loadProfileStatus()])
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(String(e)))
    } finally {
      setSaving(false)
    }
  }

  const errorAlert = error && (
    <Alert variant="destructive">
      <AlertTitle>{error.message}</AlertTitle>
      {error.problems.length > 0 && (
        <AlertDescription>
          <ul className="list-disc pl-5">{error.problems.map(p => <li key={p}>{p}</li>)}</ul>
        </AlertDescription>
      )}
    </Alert>
  )

  if (!view) return errorAlert || null
  const isSample = profile?.state === 'example'

  if (mode === 'edit') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Edit your profile</CardTitle>
          <CardDescription>
            This is data/profile.yaml. Every CV is built from it, so write facts the way you'd want them on a CV.
            Bullets need an <code>id</code>; see examples/profile.example.yaml for every option.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {errorAlert}
          {lost.length > 0 && (
            <Alert>
              <AlertTitle>The CV you have open uses things this edit removes</AlertTitle>
              <AlertDescription>
                <p>{lost.join(', ')}. That CV will fail its source check until you swap those bullets or tailor it again.</p>
                <div className="mt-2 flex gap-2">
                  <Button size="sm" onClick={() => save(true)} disabled={saving}>Save anyway</Button>
                  <Button size="sm" variant="ghost" onClick={() => setLost([])} disabled={saving}>Keep editing</Button>
                </div>
              </AlertDescription>
            </Alert>
          )}
          <Textarea
            value={yaml}
            onChange={e => { setYaml(e.target.value); setLost([]) }}
            spellCheck={false}
            wrap="off"
            className="max-h-[70vh] min-h-[32rem] font-mono text-xs [field-sizing:fixed]"
            aria-label="Profile YAML"
          />
          <div className="flex gap-3">
            <Button onClick={() => save(false)} disabled={saving || yaml === view.yaml}>
              {saving ? 'Saving…' : 'Save'}
            </Button>
            <Button variant="ghost" onClick={() => { setMode('view'); setError(null) }} disabled={saving}>Cancel</Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle>{view.name}</CardTitle>
            <CardDescription>{view.contact.join(' · ')}</CardDescription>
          </div>
          <Button size="sm" onClick={startEdit}>Edit as YAML</Button>
          <Button size="sm" variant="outline" onClick={() => setMode('import')}>
            {isSample ? 'Set up your own from your CV' : 'Replace from a CV'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {errorAlert}
        {isSample && (
          <Alert>
            <AlertTitle>This is the sample profile</AlertTitle>
            <AlertDescription>{view.name} is a fictional person. Set up your own profile from your CV to tailor real applications.</AlertDescription>
          </Alert>
        )}
        <Section title="Experience" entries={view.experience} />
        <Section title="Education" entries={view.education} />
        <Section title="Projects" entries={view.projects} />
        <Section title="Awards" entries={view.awards} />
        <Skills skills={view.skills} />
        {view.open_questions.length > 0 && (
          <section className="space-y-1">
            <h3 className="border-b pb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Open questions</h3>
            <ul className="list-disc pl-5 text-sm">{view.open_questions.map(q => <li key={q}>{q}</li>)}</ul>
          </section>
        )}
      </CardContent>
    </Card>
  )
}

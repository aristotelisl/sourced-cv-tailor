import { type ReactNode, useCallback, useEffect, useState } from 'react'

import {
  api, STATUSES, type ApplicationDetail, type ApplicationStatus, type ApplicationSummary, type ApplicationUpdate,
} from '@/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { navigate } from '@/lib/route'
import { cn } from '@/lib/utils'
import { useStore } from '@/store'

const STATUS_STYLE: Record<ApplicationStatus, string> = {
  draft: 'bg-muted text-foreground',
  applied: 'bg-sky-50 text-sky-900',
  interview: 'bg-violet-50 text-violet-900',
  offer: 'bg-emerald-50 text-emerald-900',
  rejected: 'bg-red-50 text-red-900',
  'on-hold': 'bg-amber-50 text-amber-900',
}

const formatDate = (iso: string) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

function StatusSelect({ value, onChange }: { value: ApplicationStatus; onChange: (s: ApplicationStatus) => void }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as ApplicationStatus)}
      onClick={e => e.stopPropagation()}
      aria-label="Status"
      className={cn('rounded-md border px-2 py-1 text-xs', STATUS_STYLE[value])}
    >
      {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
    </select>
  )
}

function Details({ id, onChanged }: { id: number; onChanged: () => void }) {
  const [app, setApp] = useState<ApplicationDetail | null>(null)
  const openApplication = useStore(s => s.openApplication)

  useEffect(() => { api.getApplication(id).then(setApp) }, [id])
  if (!app) return <div className="p-4 text-sm text-muted-foreground">Loading…</div>

  const save = async (update: ApplicationUpdate) => {
    setApp(await api.updateApplication(id, update))
    onChanged()
  }
  const open = async (versionId?: number) => {
    if (await openApplication(id, versionId)) navigate('tailor')
  }

  return (
    <div className="grid gap-4 p-4 md:grid-cols-2">
      <div className="space-y-3">
        <label className="block space-y-1 text-xs font-medium text-muted-foreground">
          Listing URL
          <input
            defaultValue={app.url ?? ''}
            onBlur={e => e.target.value !== (app.url ?? '') && save({ url: e.target.value || null })}
            className="block w-full rounded-md border bg-background px-2 py-1 text-sm text-foreground"
            placeholder="https://…"
          />
        </label>
        <label className="block space-y-1 text-xs font-medium text-muted-foreground">
          Notes
          <Textarea defaultValue={app.notes} onBlur={e => e.target.value !== app.notes && save({ notes: e.target.value })}
                    className="text-sm text-foreground" />
        </label>
        <label className="block space-y-1 text-xs font-medium text-muted-foreground">
          Contacts
          <Textarea defaultValue={app.contacts} placeholder="Recruiter, referrer…"
                    onBlur={e => e.target.value !== app.contacts && save({ contacts: e.target.value })}
                    className="text-sm text-foreground" />
        </label>
      </div>
      <div className="space-y-2">
        <div className="text-xs font-medium text-muted-foreground">CV versions</div>
        {app.versions.length === 0 && (
          <div className="text-sm">
            Not tailored yet. <Button size="xs" variant="outline" onClick={() => open()}>Open job</Button>
          </div>
        )}
        <ul className="space-y-1">
          {app.versions.map(v => (
            <li key={v.id} className="flex items-center gap-2 text-sm">
              <span className="w-36 shrink-0 text-muted-foreground">{formatDateTime(v.created_at)}</span>
              <span className="flex-1">
                {v.label}
                {v.id === app.cv_version_id && <span className="ml-2 text-xs text-emerald-700">sent</span>}
              </span>
              <Button size="xs" variant="outline" onClick={() => open(v.id)}>Open</Button>
              <a className="text-xs underline" href={api.versionPdfUrl(v.id)} download={`${v.filename}.pdf`}>PDF</a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

export function Tracker() {
  const [apps, setApps] = useState<ApplicationSummary[] | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { applicationId, reset } = useStore()

  const load = useCallback(() => {
    api.listApplications().then(setApps).catch(e => setError(String(e.message ?? e)))
  }, [])
  useEffect(load, [load])

  const setStatus = async (id: number, status: ApplicationStatus) => {
    await api.updateApplication(id, { status })
    load()
  }
  const remove = async (a: ApplicationSummary) => {
    if (!window.confirm(`Delete "${a.title}" at ${a.company ?? 'unknown company'} and all its CV versions?`)) return
    await api.deleteApplication(a.id)
    if (a.id === applicationId) reset()
    load()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Applications</CardTitle>
        <CardDescription>Every analysed job, with the CV versions made for it. Click a row for details.</CardDescription>
      </CardHeader>
      <CardContent>
        {error && <div className="text-sm text-red-700">{error}</div>}
        {apps?.length === 0 && <div className="text-sm text-muted-foreground">No applications yet.</div>}
        {apps && apps.length > 0 && (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr className="border-b">
                <th className="py-2 font-medium">Role</th>
                <th className="font-medium">Status</th>
                <th className="font-medium">Applied</th>
                <th className="font-medium">CVs</th>
                <th className="font-medium">Updated</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {apps.map(a => (
                <FragmentRow key={a.id} expanded={expanded === a.id}
                             details={<Details id={a.id} onChanged={load} />}>
                  <tr className="cursor-pointer border-b hover:bg-muted/50"
                      onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                    <td className="py-2">
                      <div className="font-medium">{a.title}</div>
                      <div className="text-xs text-muted-foreground">
                        {[a.company, a.location].filter(Boolean).join(' · ')}
                      </div>
                    </td>
                    <td><StatusSelect value={a.status} onChange={s => setStatus(a.id, s)} /></td>
                    <td>{a.applied_at ? formatDate(a.applied_at) : '—'}</td>
                    <td>{a.version_count}</td>
                    <td className="text-muted-foreground">{formatDate(a.updated_at)}</td>
                    <td className="text-right" onClick={e => e.stopPropagation()}>
                      <Button size="xs" variant="ghost" onClick={() => remove(a)}>Delete</Button>
                    </td>
                  </tr>
                </FragmentRow>
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  )
}

function FragmentRow({ children, expanded, details }: { children: ReactNode; expanded: boolean; details: ReactNode }) {
  return (
    <>
      {children}
      {expanded && <tr className="border-b bg-muted/30"><td colSpan={6}>{details}</td></tr>}
    </>
  )
}

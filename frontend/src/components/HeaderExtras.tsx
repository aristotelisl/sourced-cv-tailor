import { useEffect, useState } from 'react'

import { api, type ProfileSummary } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import type { ContactField } from '@/lib/cv'
import { edits, useStore } from '@/store'

const CONTACT_LABELS: Record<ContactField, string> = {
  location: 'Location', phone: 'Phone', website: 'Website', linkedin: 'LinkedIn', github: 'GitHub',
}

function Option({ checked, onChange, children }: {
  checked: boolean; onChange: (on: boolean) => void; children: React.ReactNode
}) {
  return (
    <label className="flex items-start gap-2 text-sm">
      <Checkbox className="mt-0.5" checked={checked} onCheckedChange={on => onChange(on === true)} />
      <span className="min-w-0">{children}</span>
    </label>
  )
}

/**
 * What the CV header shows: the profile's contact details (all on by default), its optional
 * lines (opt-in only: suggestions are shown, never ticked automatically) and lines typed for this CV.
 */
export function HeaderExtras() {
  const { cv, result, editCv } = useStore()
  const [profile, setProfile] = useState<ProfileSummary | null>(null)
  const [draft, setDraft] = useState('')

  useEffect(() => {
    api.profile().then(setProfile).catch(() => setProfile(null))
  }, [])

  if (!cv || !profile) return null
  const suggestions = result?.header_extra_suggestions ?? []
  const hidden = cv.hide_contact ?? []
  const profileLines = Object.values(profile.header_extras)
  const customLines = cv.header_extras.filter(x => !profileLines.includes(x))

  const addLine = () => {
    const text = draft.trim()
    if (text) editCv(c => edits.toggleHeaderExtra(c, text, true))
    setDraft('')
  }

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">Header</div>

      <div className="space-y-1.5">
        <div className="text-xs text-muted-foreground">Contact details (email is always shown)</div>
        {(Object.keys(CONTACT_LABELS) as ContactField[]).filter(f => profile.contact[f]).map(field => (
          <Option key={field} checked={!hidden.includes(field)}
                  onChange={on => editCv(c => edits.toggleContact(c, field, on))}>
            <span className="text-muted-foreground">{CONTACT_LABELS[field]}:</span>{' '}
            <span className="break-all">{profile.contact[field].replace('https://', '')}</span>
          </Option>
        ))}
      </div>

      <div className="space-y-1.5">
        <div className="text-xs text-muted-foreground">Extra lines (under phone)</div>
        {Object.entries(profile.header_extras).map(([key, text]) => {
          const suggestion = suggestions.find(s => s.key === key)
          return (
            <Option key={key} checked={cv.header_extras.includes(text)}
                    onChange={on => editCv(c => edits.toggleHeaderExtra(c, text, on))}>
              {text}
              {suggestion && <span className="ml-2 text-xs text-emerald-700">Suggested: {suggestion.reason}</span>}
            </Option>
          )
        })}
        {customLines.map(text => (
          <Option key={text} checked onChange={() => editCv(c => edits.toggleHeaderExtra(c, text, false))}>
            {text} <span className="ml-1 text-xs text-muted-foreground">(this CV only; untick to remove)</span>
          </Option>
        ))}
        <form className="flex gap-2 pt-1" onSubmit={e => { e.preventDefault(); addLine() }}>
          <input
            aria-label="New header line"
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="Add a line, e.g. Relocating to London"
            className="h-8 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm"
          />
          <Button type="submit" size="sm" variant="outline" disabled={!draft.trim()}>Add</Button>
        </form>
      </div>
    </div>
  )
}

import { useState } from 'react'

import type { Extra, ExtraKind } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useStore } from '@/store'

const KINDS: { kind: ExtraKind; label: string; recipient: string | null }[] = [
  { kind: 'cover_letter', label: 'Cover letter', recipient: 'Hiring manager (optional)' },
  { kind: 'about_me', label: 'About me', recipient: null },
  { kind: 'recruiter_message', label: 'Recruiter message', recipient: 'Recruiter, e.g. "Priya (Talent Partner)"' },
  { kind: 'referral_message', label: 'Referral request', recipient: 'Your contact, e.g. "Sam"' },
]
const LABEL = Object.fromEntries(KINDS.map(k => [k.kind, k.label])) as Record<ExtraKind, string>

const words = (text: string) => text.trim().split(/\s+/).filter(Boolean).length

function SavedExtra({ extra, recipient, notes }: { extra: Extra; recipient: string; notes: string }) {
  const { saveExtra, deleteExtra, rewriteExtra, downloadLetter, busy } = useStore()
  const [copied, setCopied] = useState(false)
  const [text, setText] = useState(extra.text)
  const [subject, setSubject] = useState(extra.subject ?? '')
  const [rewriting, setRewriting] = useState(false)
  const [feedback, setFeedback] = useState('')

  const save = () => {
    if (extra.id != null && (text !== extra.text || subject !== (extra.subject ?? ''))) {
      void saveExtra(extra.id, text, subject || null)
    }
  }
  const copy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-1.5 rounded-lg border bg-background p-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="font-medium">{LABEL[extra.kind]}</span>
        <span className="text-muted-foreground">{words(text)} words</span>
        {extra.unverified_used.length > 0 && (
          <Badge variant="outline" className="border-amber-400 text-amber-800">
            unverified: {extra.unverified_used.join(', ')}
          </Badge>
        )}
        <Button size="xs" variant="outline" className="ml-auto" onClick={copy}>{copied ? 'Copied' : 'Copy'}</Button>
        {extra.kind === 'cover_letter' && (
          <Button size="xs" variant="outline" disabled={busy !== null || !text.trim()}
                  onClick={() => downloadLetter(text, subject || null)}>
            {busy === 'letter' ? 'Making PDF…' : 'Download PDF'}
          </Button>
        )}
        <Button size="xs" variant="outline" aria-expanded={rewriting} onClick={() => setRewriting(r => !r)}>
          Rewrite…
        </Button>
        <Button size="xs" variant="ghost" aria-label="Delete text"
                onClick={() => extra.id != null && window.confirm('Delete this text?') && deleteExtra(extra.id)}>
          Delete
        </Button>
      </div>
      {extra.subject != null && (
        <input value={subject} onChange={e => setSubject(e.target.value)} onBlur={save} aria-label="Subject"
               className="w-full rounded-md border px-2 py-1 text-sm" />
      )}
      <Textarea value={text} onChange={e => setText(e.target.value)} onBlur={save} className="text-sm"
                aria-label={`${LABEL[extra.kind]} text`} />
      {rewriting && (
        <div className="space-y-1.5 rounded-md bg-muted/50 p-2">
          <Textarea value={feedback} onChange={e => setFeedback(e.target.value)} className="min-h-16 text-sm"
                    aria-label="Rewrite feedback"
                    placeholder="What should change? e.g. shorter, less formal, lead with my current job, mention I can start in January…" />
          <div className="flex items-center gap-2">
            <Button size="sm" disabled={busy !== null || !feedback.trim()}
                    onClick={async () => {
                      await rewriteExtra(extra.kind, text, feedback.trim(), recipient, notes)
                      if (!useStore.getState().error) { setFeedback(''); setRewriting(false) }
                    }}>
              {busy === 'rewrite' ? 'Rewriting… (about 20 seconds)' : 'Rewrite'}
            </Button>
            <span className="text-xs text-muted-foreground">
              The new version appears above; this one is kept. Facts you state here may be used.
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

/** Cover letter, about-me blurb and messages. Same no-invention rule as the CV, checked in the backend. */
export function Extras() {
  const { extras, busy, generateExtra, analysis } = useStore()
  const [kind, setKind] = useState<ExtraKind>('cover_letter')
  const [recipient, setRecipient] = useState('')
  const [notes, setNotes] = useState('')
  if (!analysis) return null
  const current = KINDS.find(k => k.kind === kind)!

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">Cover letter and messages</div>
      <div className="flex flex-wrap gap-1">
        {KINDS.map(k => (
          <button key={k.kind} onClick={() => setKind(k.kind)}
                  className={cn('rounded-md border px-2 py-1 text-xs',
                    k.kind === kind ? 'border-foreground bg-foreground text-background' : 'bg-background')}>
            {k.label}
          </button>
        ))}
      </div>
      {current.recipient && (
        <input value={recipient} onChange={e => setRecipient(e.target.value)} placeholder={current.recipient}
               aria-label="Recipient" className="w-full rounded-md border bg-background px-2 py-1 text-sm" />
      )}
      <Textarea value={notes} onChange={e => setNotes(e.target.value)} className="text-sm" aria-label="Notes for the writer"
                placeholder="Optional notes: why this company, where you heard of it, who referred you… Facts here may be used." />
      <Button onClick={() => generateExtra(kind, current.recipient ? recipient : '', notes)} disabled={busy !== null}>
        {busy === 'extra' ? 'Writing… (about 20 seconds)' : `Write ${current.label.toLowerCase()}`}
      </Button>
      {extras.map(e => <SavedExtra key={e.id ?? e.text} extra={e} recipient={recipient} notes={notes} />)}
    </div>
  )
}

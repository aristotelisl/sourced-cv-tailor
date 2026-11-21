import { useState } from 'react'

import { ApiError, api, type ProfileProposal } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'
import { useStore } from '@/store'

function List({ title, items, className }: { title: string; items: string[]; className?: string }) {
  if (!items.length) return null
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      <ul className={`mt-1 list-disc space-y-0.5 pl-5 text-sm ${className ?? ''}`}>
        {items.map(item => <li key={item}>{item}</li>)}
      </ul>
    </div>
  )
}

function Diff({ diff }: { diff: string }) {
  const lines = diff.split('\n').filter(l => l && !l.startsWith('---') && !l.startsWith('+++'))
  return (
    <pre aria-label="Profile diff" className="max-h-72 overflow-auto rounded-md border bg-background p-2 text-[11px] leading-snug">
      {lines.map((line, i) => (
        <div key={i} className={cn(
          line.startsWith('+') && 'bg-emerald-50 text-emerald-900',
          line.startsWith('-') && 'bg-red-50 text-red-900',
          line.startsWith('@@') && 'text-muted-foreground',
        )}>{line}</div>
      ))}
    </pre>
  )
}

type Step = 'idle' | 'answering' | 'proposing' | 'review' | 'saving' | 'saved'

/** Answer a question: the model proposes profile.yaml edits from the answer, you check the diff, then save. */
function Question({ question }: { question: string }) {
  const { analysis, loadBank } = useStore()
  const [step, setStep] = useState<Step>('idle')
  const [answer, setAnswer] = useState('')
  const [proposal, setProposal] = useState<ProfileProposal | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  const fail = (e: unknown, back: Step) => {
    setError(e instanceof ApiError ? e : new ApiError(String(e)))
    setStep(back)
  }
  const propose = async () => {
    setStep('proposing')
    setError(null)
    try {
      setProposal(await api.answerQuestion(question, answer, analysis))
      setStep('review')
    } catch (e) {
      fail(e, 'answering')
    }
  }
  const save = async () => {
    if (!proposal) return
    setStep('saving')
    setError(null)
    try {
      await api.applyProfileEdits(question, answer, proposal)
      setStep('saved')
      void loadBank(true)
    } catch (e) {
      fail(e, 'review')
    }
  }

  return (
    <li className="space-y-1.5">
      <div className="flex items-start gap-2">
        <span className="flex-1">{question}</span>
        {step === 'idle' && <Button size="xs" variant="outline" onClick={() => setStep('answering')}>Answer</Button>}
        {step === 'saved' && <span className="text-xs text-emerald-700">Saved to profile.yaml</span>}
      </div>
      {(step === 'answering' || step === 'proposing') && (
        <div className="space-y-1.5">
          <Textarea value={answer} onChange={e => setAnswer(e.target.value)} aria-label={`Answer: ${question}`}
                    className="text-sm" placeholder="Your answer, in your own words. Only what you write here can go into the profile." />
          <div className="flex gap-2">
            <Button size="xs" onClick={propose} disabled={!answer.trim() || step === 'proposing'}>
              {step === 'proposing' ? 'Preparing changes… (about 10 s)' : 'Preview profile changes'}
            </Button>
            <Button size="xs" variant="ghost" onClick={() => setStep('idle')}>Cancel</Button>
          </div>
        </div>
      )}
      {(step === 'review' || step === 'saving') && proposal && (
        <div className="space-y-1.5 rounded-md border bg-muted/40 p-2">
          <div className="text-xs">{proposal.summary}</div>
          {proposal.diff ? <Diff diff={proposal.diff} /> : <div className="text-xs text-muted-foreground">No changes to the profile.</div>}
          <div className="flex gap-2">
            {proposal.diff && (
              <Button size="xs" onClick={save} disabled={step === 'saving'}>
                {step === 'saving' ? 'Saving…' : 'Save to profile.yaml'}
              </Button>
            )}
            <Button size="xs" variant="ghost" onClick={() => setStep('answering')}>Edit answer</Button>
            <Button size="xs" variant="ghost" onClick={() => setStep('idle')}>Discard</Button>
          </div>
        </div>
      )}
      {step === 'saved' && (
        <div className="text-xs text-muted-foreground">
          New facts are now in your profile: use Add from profile in the editor, or tailor again.
        </div>
      )}
      {error && (
        <div className="text-xs text-red-800">
          {error.message}
          {error.problems.length > 0 && <ul className="list-disc pl-4">{error.problems.map(p => <li key={p}>{p}</li>)}</ul>}
        </div>
      )}
    </li>
  )
}

export function GapReport() {
  const gaps = useStore(s => s.cv?.gap_report)
  if (!gaps) return null
  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">Gap report</div>
      <List title="Red flags" items={gaps.flags} className="text-red-800" />
      <List title="Missing must-haves" items={gaps.must_have_missing} />
      <List title="Missing nice-to-haves" items={gaps.nice_to_have_missing} />
      <List title="Unverified facts used" items={gaps.unverified_used} className="text-amber-800" />
      {gaps.questions.length > 0 && (
        <div>
          <div className="text-xs font-medium text-muted-foreground">Questions for you (answers can update your profile)</div>
          <ul className="mt-1 space-y-2 text-sm">
            {gaps.questions.map(q => <Question key={q} question={q} />)}
          </ul>
        </div>
      )}
    </div>
  )
}

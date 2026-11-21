import { useState } from 'react'

import { ApiError, api, type ProfileImportResult } from '@/api/client'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { navigate } from '@/lib/route'
import { useStore } from '@/store'

const MIN_TEXT = 50 // the backend refuses less (backend/profile_import/text.py)
const ACCEPT = '.pdf,.docx,.txt,.md'

type Step = 'choose' | 'reading' | 'review' | 'saving'

async function toBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer())
  let binary = ''
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
  return btoa(binary)
}

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? '' : 's'}`
}

function summary({ counts: c }: ProfileImportResult) {
  return [
    `${plural(c.jobs ?? 0, 'job')} (${plural(c.bullets ?? 0, 'bullet')})`,
    plural(c.education ?? 0, 'degree'), plural(c.projects ?? 0, 'project'), plural(c.awards ?? 0, 'award'),
    plural(c.skills ?? 0, 'skill'),
  ].join(', ')
}

/**
 * Read the user's CV into a profile.yaml they check before saving. On first run it also offers the sample
 * profile; `onCancel` (from the Profile page) goes back to the profile they have instead.
 */
export function ProfileSetup({ onCancel }: { onCancel?: () => void }) {
  const { profile, chooseSample, profileReplaced } = useStore()
  const [step, setStep] = useState<Step>('choose')
  const [file, setFile] = useState<File | null>(null)
  const [pasting, setPasting] = useState(false)
  const [text, setText] = useState('')
  const [result, setResult] = useState<ProfileImportResult | null>(null)
  const [yaml, setYaml] = useState('')
  const [error, setError] = useState<ApiError | null>(null)

  const hasOwn = profile?.state === 'own'
  const ready = pasting ? text.trim().length >= MIN_TEXT : file !== null

  const fail = (e: unknown, back: Step) => {
    setError(e instanceof ApiError ? e : new ApiError(String(e)))
    setStep(back)
  }

  const read = async () => {
    setStep('reading')
    setError(null)
    try {
      const res = pasting
        ? await api.importCv({ text })
        : await api.importCv({ filename: file!.name, content_base64: await toBase64(file!) })
      setResult(res)
      setYaml(res.yaml)
      setStep('review')
    } catch (e) {
      fail(e, 'choose')
    }
  }

  const save = async () => {
    setStep('saving')
    setError(null)
    try {
      const res = await api.saveProfile(yaml, { backup: true })
      profileReplaced(res.status)
      navigate({ page: 'new' })
    } catch (e) {
      fail(e, 'review')
    }
  }

  const sample = async () => {
    await chooseSample()
    navigate({ page: 'new' })
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

  if (step === 'review' || step === 'saving') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Check your profile</CardTitle>
          <CardDescription>
            Found {result && summary(result)}. This is your profile.yaml: every CV is built from it, and only
            from it. Fix anything that's wrong, and add what your CV leaves out (more bullets per job, tools you
            used, numbers). You can edit it later too.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {errorAlert}
          {result && result.warnings.length > 0 && (
            <Alert>
              <AlertTitle>Some things couldn't be matched to your CV word for word</AlertTitle>
              <AlertDescription>
                <ul className="list-disc space-y-0.5 pl-5">{result.warnings.map(w => <li key={w}>{w}</li>)}</ul>
                <p className="mt-2">
                  Bullets marked <code>verified: false</code> get a warning badge until you confirm them.
                </p>
              </AlertDescription>
            </Alert>
          )}
          <Textarea
            value={yaml}
            onChange={e => setYaml(e.target.value)}
            spellCheck={false}
            wrap="off"
            className="max-h-[70vh] min-h-[32rem] font-mono text-xs [field-sizing:fixed]"
            aria-label="Profile YAML"
          />
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={save} disabled={step === 'saving'}>
              {step === 'saving' ? 'Saving…' : 'Save as my profile'}
            </Button>
            <Button variant="ghost" onClick={() => { setStep('choose'); setError(null) }} disabled={step === 'saving'}>
              Start over
            </Button>
            {hasOwn && (
              <span className="text-xs text-muted-foreground">
                This replaces your current profile. A copy of the old one is kept in the data folder.
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    )
  }

  const reading = step === 'reading'
  return (
    <Card>
      <CardHeader>
        <CardTitle>{hasOwn ? 'Replace your profile from a CV' : 'Set up your profile'}</CardTitle>
        <CardDescription>
          Every CV the app makes comes from your profile, so start by uploading the CV you have now. It's copied
          in as it is: nothing is added that your CV doesn't say, and you check everything before it's saved.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {errorAlert}
        {pasting ? (
          <Textarea
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Paste the text of your CV here…"
            className="min-h-80 font-mono text-xs"
            aria-label="CV text"
            disabled={reading}
          />
        ) : (
          <label className="flex cursor-pointer flex-col items-center gap-1 rounded-lg border border-dashed bg-background px-6 py-10 text-center text-sm hover:bg-muted/50">
            <span className="font-medium">{file ? file.name : 'Choose your CV'}</span>
            <span className="text-xs text-muted-foreground">PDF, Word (.docx) or text</span>
            <input type="file" accept={ACCEPT} className="sr-only" aria-label="CV file" disabled={reading}
                   onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </label>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={read} disabled={!ready || reading}>
            {reading ? 'Reading your CV…' : 'Read my CV'}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPasting(!pasting)} disabled={reading}>
            {pasting ? 'Upload a file instead' : 'Paste the text instead'}
          </Button>
          {reading && <span className="text-xs text-muted-foreground">This takes up to a minute.</span>}
        </div>

        <div className="border-t pt-4 text-sm">
          {onCancel ? (
            <Button variant="outline" onClick={onCancel} disabled={reading}>
              {hasOwn ? 'Keep my current profile' : 'Back to the sample profile'}
            </Button>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="outline" onClick={sample} disabled={reading}>Explore with the sample profile</Button>
              <span className="text-xs text-muted-foreground">
                Try the app as Jordan Avery, a fictional developer. You can set up your own profile any time.
              </span>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

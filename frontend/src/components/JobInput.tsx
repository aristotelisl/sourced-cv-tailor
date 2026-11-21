import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import { useStore } from '@/store'

const MIN_LENGTH = 50 // matches AnalyseRequest.text min_length

export function JobInput() {
  const { jobText, setJobText, analyse, busy } = useStore()
  const tooShort = jobText.trim().length < MIN_LENGTH

  return (
    <Card>
      <CardHeader>
        <CardTitle>New application</CardTitle>
        <CardDescription>Paste the full job listing. The analysis takes a few seconds.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Textarea
          value={jobText}
          onChange={e => setJobText(e.target.value)}
          placeholder="Paste the job listing here…"
          className="min-h-80 font-mono text-xs"
          aria-label="Job listing"
        />
        <div className="flex items-center gap-3">
          <Button onClick={analyse} disabled={tooShort || busy !== null}>
            {busy === 'analyse' ? 'Analysing…' : 'Analyse'}
          </Button>
          {tooShort && jobText && <span className="text-xs text-muted-foreground">Paste the whole listing.</span>}
        </div>
      </CardContent>
    </Card>
  )
}

import type { JobAnalysis, RequirementCoverage } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { useStore } from '@/store'

const STATUS_STYLE: Record<RequirementCoverage['status'], string> = {
  covered: 'border-emerald-300 bg-emerald-50 text-emerald-900',
  partial: 'border-amber-300 bg-amber-50 text-amber-900',
  missing: 'border-red-300 bg-red-50 text-red-900',
}

function formatSalary(salary: JobAnalysis['salary']): string | null {
  if (!salary) return null
  const fmt = (n: number | null | undefined) => (n == null ? '?' : n.toLocaleString('en-GB'))
  return `${fmt(salary.min)}–${fmt(salary.max)} ${salary.currency} / ${salary.period}`
}

function Chips({ title, items, coverage }: { title: string; items: string[]; coverage: RequirementCoverage[] }) {
  if (!items.length) return null
  return (
    <div className="space-y-1.5">
      <div className="text-xs font-medium text-muted-foreground">{title}</div>
      <div className="flex flex-wrap gap-1.5">
        {items.map(item => {
          const c = coverage.find(x => x.requirement === item)
          return (
            <span
              key={item}
              title={c?.note}
              className={cn('rounded-md border px-2 py-0.5 text-xs',
                c ? STATUS_STYLE[c.status] : 'border-border bg-background')}
            >
              {item}
            </span>
          )
        })}
      </div>
    </div>
  )
}

export function AnalysisPanel() {
  const { analysis, result, edited, busy, tailor } = useStore()
  if (!analysis) return null
  const coverage = result?.coverage ?? []
  const facts = [analysis.location, analysis.remote, analysis.seniority, analysis.years_required && `${analysis.years_required} yrs`,
    formatSalary(analysis.salary)].filter(Boolean)

  const onTailor = () => {
    if (edited && !window.confirm('Tailoring again replaces your edits. Continue?')) return
    void tailor()
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{analysis.title}</CardTitle>
        <CardDescription>{analysis.company ?? 'Company not named'} · {facts.join(' · ')}</CardDescription>
        <CardAction>
          <Button onClick={onTailor} disabled={busy !== null} variant={result ? 'outline' : 'default'}>
            {busy === 'tailor' ? 'Tailoring… (about a minute)' : result ? 'Tailor again' : 'Tailor CV'}
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{analysis.role_family}</Badge>
          {analysis.right_to_work && <Badge variant="outline">Right to work: {analysis.right_to_work}</Badge>}
          {coverage.length > 0 && (
            <span className="ml-auto text-xs text-muted-foreground">
              <span className="text-emerald-700">■</span> covered <span className="text-amber-600">■</span> partial{' '}
              <span className="text-red-600">■</span> missing (hover for details)
            </span>
          )}
        </div>
        <Chips title="Must have" items={analysis.must_have} coverage={coverage} />
        <Chips title="Nice to have" items={analysis.nice_to_have} coverage={coverage} />
        <Chips title="Stack" items={analysis.stack} coverage={[]} />
      </CardContent>
    </Card>
  )
}

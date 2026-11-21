import { ArrowDown, ArrowLeftRight, ArrowUp, GripVertical, Plus, Sparkles, Trash2, X } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ApiError, api, type BankItem, type Bullet, type BulletOption, type Entry, type Section } from '@/api/client'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import type { BulletRef, EntryRef } from '@/lib/cv'
import { useDragReorder } from '@/lib/drag'
import { cn } from '@/lib/utils'
import { edits, useStore } from '@/store'

function entryHeading(e: Entry): string {
  const middle = e.middle ?? [e.middle_prefix, e.middle_link_text, e.middle_suffix].filter(Boolean).join('')
  return [e.left, middle, e.right].filter(Boolean).join(' · ')
}

function UnverifiedBadge({ ids }: { ids: string[] }) {
  if (!ids.length) return null
  return (
    <Badge variant="outline" className="border-amber-400 text-amber-800" title="verified: false in profile.yaml">
      unverified: {ids.join(', ')}
    </Badge>
  )
}

/** Ask the model for three rewrites of one bullet, checked against the profile like a full tailoring run. */
function RewritePanel({ entry, at, onClose }: { entry: Entry; at: BulletRef; onClose: () => void }) {
  const { analysis, editCv } = useStore()
  const [hint, setHint] = useState('')
  const [options, setOptions] = useState<BulletOption[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const bullets = entry.bullets ?? []

  const suggest = async () => {
    if (!analysis) return
    setLoading(true)
    setError(null)
    try {
      setOptions(await api.rewriteBullet({
        job: analysis, entry: entry.source, bullet: bullets[at.bullet], hint: hint || null,
        others: bullets.filter((_, i) => i !== at.bullet),
      }))
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError(String(e)))
    } finally {
      setLoading(false)
    }
  }
  const use = (o: BulletOption) => {
    editCv(cv => edits.addUnverified(edits.replaceBullet(cv, at, o.bullet), o.unverified))
    onClose()
  }

  return (
    <div className="space-y-2 rounded-md border bg-muted/40 p-2">
      <div className="flex gap-2">
        <input value={hint} onChange={e => setHint(e.target.value)} aria-label="Rewrite hint"
               onKeyDown={e => e.key === 'Enter' && !loading && void suggest()}
               placeholder='Optional: "shorter", "lead with the APIs", "more backend"…'
               className="min-w-0 flex-1 rounded-md border bg-background px-2 py-1 text-xs" />
        <Button size="xs" onClick={suggest} disabled={loading}>
          {loading ? 'Writing… (about 15 s)' : options ? 'Try again' : 'Suggest rewrites'}
        </Button>
        <Button size="icon-xs" variant="ghost" aria-label="Close rewrite" onClick={onClose}><X /></Button>
      </div>
      {error && (
        <div className="text-xs text-red-800">
          {error.message}
          {error.problems.length > 0 && <ul className="list-disc pl-4">{error.problems.map(p => <li key={p}>{p}</li>)}</ul>}
        </div>
      )}
      {options?.map((o, i) => (
        <div key={i} className="flex items-start gap-2 rounded border bg-background p-2 text-xs">
          <div className="flex-1 space-y-1">
            <div className="text-sm">{o.bullet.text}{o.bullet.tech && <span className="italic"> ({o.bullet.tech})</span>}</div>
            <div className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
              source: {o.bullet.source} <UnverifiedBadge ids={o.unverified} />
            </div>
          </div>
          <Button size="xs" variant="outline" onClick={() => use(o)}>Use</Button>
        </div>
      ))}
    </div>
  )
}

/** Pick a fact from profile.yaml for this entry: swaps the bullet (`at` set) or adds a new one. */
function BankPanel({ entry, entryRef, at, onClose }: { entry: Entry; entryRef: EntryRef; at?: BulletRef; onClose: () => void }) {
  const { bank, loadBank, editCv } = useStore()
  useEffect(() => { void loadBank() }, [loadBank])
  const items = bank?.[entry.source] ?? []
  const cited = edits.citedIds(entry.bullets ?? [])
  const current = at ? (entry.bullets ?? [])[at.bullet] : undefined

  const pick = (item: BankItem) => {
    // The profile's own wording, verbatim: nothing new to check. Keep the italic tech line on a swap.
    const bullet: Bullet = { source: item.id, text: item.text, tech: current?.tech ?? null }
    editCv(cv => {
      const next = at ? edits.replaceBullet(cv, at, bullet) : edits.addBullet(cv, entryRef, bullet)
      return edits.addUnverified(next, item.verified ? [] : [item.id])
    })
    onClose()
  }

  return (
    <div className="space-y-1 rounded-md border bg-muted/40 p-2">
      <div className="flex items-center text-xs text-muted-foreground">
        <span className="flex-1">{at ? 'Swap with a fact from your profile' : 'Add a fact from your profile'} (profile wording, edit or rewrite after)</span>
        <Button size="icon-xs" variant="ghost" aria-label="Close profile facts" onClick={onClose}><X /></Button>
      </div>
      {!bank && <div className="text-xs text-muted-foreground">Loading…</div>}
      {items.map(item => {
        const used = cited.has(item.id)
        return (
          <button key={item.id} disabled={used} onClick={() => pick(item)}
                  className="block w-full rounded border bg-background px-2 py-1 text-left text-xs enabled:hover:border-foreground disabled:opacity-50">
            <span className="font-mono text-[10px] text-muted-foreground">{item.id}{used && ' · on CV'}{!item.verified && ' · unverified'}</span>
            <div>{item.text}</div>
          </button>
        )
      })}
    </div>
  )
}

function BulletRow({ entry, at, count, drag }: {
  entry: Entry; at: BulletRef; count: number; drag: ReturnType<typeof useDragReorder>
}) {
  const editCv = useStore(s => s.editCv)
  const unverified = useStore(s => s.cv?.gap_report.unverified_used ?? [])
  const canSwap = useStore(s => (s.bank?.[entry.source]?.length ?? 0) > 0)
  const [panel, setPanel] = useState<null | 'rewrite' | 'swap'>(null)
  const b = (entry.bullets ?? [])[at.bullet]
  const toggle = (p: 'rewrite' | 'swap') => setPanel(cur => (cur === p ? null : p))

  return (
    <div {...drag.target(at.bullet)}
         className={cn('group space-y-1.5 rounded-md', drag.over === at.bullet && 'ring-2 ring-primary/50')}>
      <div className="flex gap-1.5">
        <div {...drag.handle(at.bullet)} aria-label={`Drag bullet ${at.bullet + 1}`}
             className="cursor-grab pt-2 text-muted-foreground/50 hover:text-foreground active:cursor-grabbing">
          <GripVertical className="size-4" />
        </div>
        <div className="flex-1 space-y-1">
          <Textarea value={b.text} onChange={e => editCv(cv => edits.editBullet(cv, at, e.target.value))}
                    className="min-h-0 text-sm" aria-label={`Bullet ${at.bullet + 1}`} />
          <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
            {b.tech && <span className="italic">({b.tech})</span>}
            <span>source: {b.source}</span>
            <UnverifiedBadge ids={edits.unverifiedParts(b.source, unverified)} />
            <span className="ml-auto flex gap-1">
              <Button size="xs" variant={panel === 'rewrite' ? 'secondary' : 'ghost'} onClick={() => toggle('rewrite')}>
                <Sparkles /> Rewrite
              </Button>
              {canSwap && (
                <Button size="xs" variant={panel === 'swap' ? 'secondary' : 'ghost'} onClick={() => toggle('swap')}>
                  <ArrowLeftRight /> Swap
                </Button>
              )}
            </span>
          </div>
        </div>
        <div className="flex flex-col opacity-40 transition-opacity group-hover:opacity-100">
          <Button size="icon-xs" variant="ghost" aria-label="Move up" disabled={at.bullet === 0}
                  onClick={() => editCv(cv => edits.moveBullet(cv, at, at.bullet - 1))}><ArrowUp /></Button>
          <Button size="icon-xs" variant="ghost" aria-label="Move down" disabled={at.bullet === count - 1}
                  onClick={() => editCv(cv => edits.moveBullet(cv, at, at.bullet + 1))}><ArrowDown /></Button>
          <Button size="icon-xs" variant="ghost" aria-label="Remove bullet"
                  onClick={() => editCv(cv => edits.removeBullet(cv, at))}><Trash2 /></Button>
        </div>
      </div>
      {panel === 'rewrite' && <RewritePanel entry={entry} at={at} onClose={() => setPanel(null)} />}
      {panel === 'swap' && <BankPanel entry={entry} entryRef={at} at={at} onClose={() => setPanel(null)} />}
    </div>
  )
}

function EntryEditor({ entry, at, drag }: { entry: Entry; at: EntryRef; drag: ReturnType<typeof useDragReorder> }) {
  const editCv = useStore(s => s.editCv)
  const hasBank = useStore(s => (s.bank?.[entry.source]?.length ?? 0) > 0)
  const [adding, setAdding] = useState(false)
  const bullets = entry.bullets ?? []
  const bulletDrag = useDragReorder(`bullets:${at.section}:${at.entry}`,
    (from, to) => editCv(cv => edits.moveBullet(cv, { ...at, bullet: from }, to)))

  return (
    <div {...drag.target(at.entry)}
         className={cn('space-y-2 rounded-md', drag.over === at.entry && 'ring-2 ring-primary/50')}>
      <div className="flex items-center gap-1.5 text-sm font-medium">
        <span {...drag.handle(at.entry)} aria-label={`Drag ${entry.left}`}
              className="cursor-grab text-muted-foreground/50 hover:text-foreground active:cursor-grabbing">
          <GripVertical className="size-4" />
        </span>
        <span className="flex-1">{entryHeading(entry)}</span>
        {hasBank && !adding && (
          <Button size="xs" variant="ghost" onClick={() => setAdding(true)}><Plus /> Add from profile</Button>
        )}
      </div>
      {bullets.map((_, bi) => (
        <BulletRow key={bi} entry={entry} at={{ ...at, bullet: bi }} count={bullets.length} drag={bulletDrag} />
      ))}
      {adding && <BankPanel entry={entry} entryRef={at} onClose={() => setAdding(false)} />}
    </div>
  )
}

function SkillsEditor({ section, index }: { section: Section; index: number }) {
  const editCv = useStore(s => s.editCv)
  return (
    <ul className="space-y-1 text-sm">
      {(section.skills ?? []).map((g, gi) => (
        <li key={g.label} className="flex flex-wrap items-center gap-1">
          <span className="mr-1 font-medium">{g.label}:</span>
          {g.items.map((item, ii) => (
            <span key={item} className="inline-flex items-center gap-0.5 rounded border bg-background px-1.5 text-xs">
              {item}
              <button aria-label={`Remove ${item}`} className="text-muted-foreground hover:text-foreground"
                      onClick={() => editCv(cv => edits.removeSkill(cv, index, gi, ii))}>
                <X className="size-3" />
              </button>
            </span>
          ))}
        </li>
      ))}
    </ul>
  )
}

function SectionEditor({ section, si, count, drag }: {
  section: Section; si: number; count: number; drag: ReturnType<typeof useDragReorder>
}) {
  const editCv = useStore(s => s.editCv)
  const entryDrag = useDragReorder(`entries:${si}`,
    (from, to) => editCv(cv => edits.moveEntry(cv, { section: si, entry: from }, to)))

  return (
    <section {...drag.target(si)}
             className={cn('space-y-3 rounded-md', drag.over === si && 'ring-2 ring-primary/50')}>
      <div className="flex items-center gap-1 border-b pb-1">
        <span {...drag.handle(si)} aria-label={`Drag ${section.title} section`}
              className="cursor-grab text-muted-foreground/50 hover:text-foreground active:cursor-grabbing">
          <GripVertical className="size-4" />
        </span>
        <h3 className="flex-1 text-sm font-semibold">{section.title}</h3>
        <Button size="icon-xs" variant="ghost" aria-label={`Move ${section.title} up`} disabled={si === 0}
                onClick={() => editCv(c => edits.moveSection(c, si, si - 1))}><ArrowUp /></Button>
        <Button size="icon-xs" variant="ghost" aria-label={`Move ${section.title} down`} disabled={si === count - 1}
                onClick={() => editCv(c => edits.moveSection(c, si, si + 1))}><ArrowDown /></Button>
      </div>
      {(section.entries ?? []).map((entry, ei) => (
        <EntryEditor key={entry.source} entry={entry} at={{ section: si, entry: ei }} drag={entryDrag} />
      ))}
      {(section.skills ?? []).length > 0 && <SkillsEditor section={section} index={si} />}
    </section>
  )
}

export function Editor() {
  const { cv, editCv, loadBank } = useStore()
  const sectionDrag = useDragReorder('sections', (from, to) => editCv(c => edits.moveSection(c, from, to)))
  useEffect(() => { void loadBank() }, [loadBank])
  if (!cv) return null
  return (
    <div className="space-y-5">
      <p className="text-xs text-muted-foreground">
        Drag <GripVertical className="inline size-3" /> to reorder. Rewrite asks the model for alternatives checked against
        your profile; Swap uses a fact from your profile as written.
      </p>
      {cv.sections.map((section, si) => (
        <SectionEditor key={section.title} section={section} si={si} count={cv.sections.length} drag={sectionDrag} />
      ))}
    </div>
  )
}

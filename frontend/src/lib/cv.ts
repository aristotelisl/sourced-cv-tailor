// Pure, immutable edits to a TailoredCV. The store calls these; tests cover them directly.
import type { Bullet, TailoredCV } from '@/api/client'

export interface EntryRef {
  section: number
  entry: number
}

export interface BulletRef extends EntryRef {
  bullet: number
}

/** Move one item to another index (drag and drop, or ±1 for the arrow buttons). */
export function move<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length || from === to) return items
  const next = [...items]
  const [item] = next.splice(from, 1)
  next.splice(to, 0, item)
  return next
}

type Entries = NonNullable<TailoredCV['sections'][number]['entries']>
type Bullets = NonNullable<Entries[number]['bullets']>

function updateEntries(cv: TailoredCV, section: number, fn: (entries: Entries) => Entries): TailoredCV {
  return {
    ...cv,
    sections: cv.sections.map((s, si) => si !== section ? s : { ...s, entries: fn(s.entries ?? []) }),
  }
}

function updateBullets(cv: TailoredCV, ref: EntryRef, fn: (bullets: Bullets) => Bullets): TailoredCV {
  return updateEntries(cv, ref.section, entries =>
    entries.map((e, ei) => ei !== ref.entry ? e : { ...e, bullets: fn(e.bullets ?? []) }))
}

export function editBullet(cv: TailoredCV, ref: BulletRef, text: string): TailoredCV {
  return updateBullets(cv, ref, bullets => bullets.map((b, i) => i === ref.bullet ? { ...b, text } : b))
}

export function replaceBullet(cv: TailoredCV, ref: BulletRef, bullet: Bullet): TailoredCV {
  return updateBullets(cv, ref, bullets => bullets.map((b, i) => i === ref.bullet ? bullet : b))
}

export function addBullet(cv: TailoredCV, ref: EntryRef, bullet: Bullet): TailoredCV {
  return updateBullets(cv, ref, bullets => [...bullets, bullet])
}

export function moveBullet(cv: TailoredCV, ref: BulletRef, to: number): TailoredCV {
  return updateBullets(cv, ref, bullets => move(bullets, ref.bullet, to))
}

export function removeBullet(cv: TailoredCV, ref: BulletRef): TailoredCV {
  return updateBullets(cv, ref, bullets => bullets.filter((_, i) => i !== ref.bullet))
}

export function moveEntry(cv: TailoredCV, ref: EntryRef, to: number): TailoredCV {
  return updateEntries(cv, ref.section, entries => move(entries, ref.entry, to))
}

export function moveSection(cv: TailoredCV, index: number, to: number): TailoredCV {
  return { ...cv, sections: move(cv.sections, index, to) }
}

export function removeSkill(cv: TailoredCV, section: number, group: number, item: number): TailoredCV {
  return {
    ...cv,
    sections: cv.sections.map((s, si) => si !== section ? s : {
      ...s,
      skills: (s.skills ?? [])
        .map((g, gi) => gi !== group ? g : { ...g, items: g.items.filter((_, ii) => ii !== item) })
        .filter(g => g.items.length > 0),
    }),
  }
}

export function toggleHeaderExtra(cv: TailoredCV, text: string, on: boolean): TailoredCV {
  const rest = cv.header_extras.filter(x => x !== text)
  return { ...cv, header_extras: on ? [...rest, text] : rest }
}

export type ContactField = TailoredCV['hide_contact'][number]

/** "CV_Jordan_Avery_Systems" -> "Cover_Letter_Jordan_Avery_Systems". */
export function letterFilename(cvFilename: string | undefined): string {
  if (!cvFilename) return 'Cover_Letter'
  return /^CV(?=[_.-]|$)/.test(cvFilename) ? cvFilename.replace(/^CV/, 'Cover_Letter') : `Cover_Letter_${cvFilename}`
}

/** Show or hide one of the profile's contact details in this CV's header. */
export function toggleContact(cv: TailoredCV, field: ContactField, show: boolean): TailoredCV {
  const rest = (cv.hide_contact ?? []).filter(x => x !== field)
  return { ...cv, hide_contact: show ? rest : [...rest, field] }
}

/** Record ids marked `verified: false` that a new bullet brought in, so the gap report lists them. */
export function addUnverified(cv: TailoredCV, ids: string[]): TailoredCV {
  const known = cv.gap_report.unverified_used
  const added = ids.filter(id => !known.includes(id))
  return added.length ? { ...cv, gap_report: { ...cv.gap_report, unverified_used: [...known, ...added] } } : cv
}

/** Sources of a bullet that the profile marks `verified: false`. */
export function unverifiedParts(source: string, unverified: string[]): string[] {
  return source.split('+').filter(part => unverified.includes(part))
}

/** Profile ids already cited by an entry's bullets. */
export function citedIds(bullets: Bullet[]): Set<string> {
  return new Set(bullets.flatMap(b => b.source.split('+')))
}

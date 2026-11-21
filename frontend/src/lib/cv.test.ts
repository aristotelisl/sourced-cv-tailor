import { describe, expect, it } from 'vitest'

import { errorFromBody, type TailoredCV } from '@/api/client'
import * as edits from './cv'

function cv(): TailoredCV {
  return {
    filename: 'CV',
    header_extras: [],
    hide_contact: [],
    layout: {},
    gap_report: { must_have_missing: [], nice_to_have_missing: [], unverified_used: ['b2'], questions: [], flags: [] },
    sections: [
      { title: 'Employment', entries: [{ source: 'job', left: 'Dev', bullets: [
        { source: 'b1', text: 'one' }, { source: 'b2+b3', text: 'two' }, { source: 'b3', text: 'three' },
      ] }], skills: [] },
      { title: 'Skills', entries: [], skills: [{ label: 'Frontend', items: ['React', 'Vite'] }, { label: 'AI', items: ['RAG'] }] },
    ],
  }
}
const texts = (c: TailoredCV) => c.sections[0].entries![0].bullets!.map(b => b.text)
const ref = (bullet: number) => ({ section: 0, entry: 0, bullet })

describe('cv edits', () => {
  it('edits a bullet without mutating the original', () => {
    const original = cv()
    const next = edits.editBullet(original, ref(1), 'TWO')
    expect(texts(next)).toEqual(['one', 'TWO', 'three'])
    expect(texts(original)).toEqual(['one', 'two', 'three'])
    expect(next.sections[0].entries![0].bullets![1].source).toBe('b2+b3')
  })

  it('moves bullets to any index and ignores moves past the ends', () => {
    expect(texts(edits.moveBullet(cv(), ref(0), 1))).toEqual(['two', 'one', 'three'])
    expect(texts(edits.moveBullet(cv(), ref(0), 2))).toEqual(['two', 'three', 'one'])
    expect(texts(edits.moveBullet(cv(), ref(2), 0))).toEqual(['three', 'one', 'two'])
    expect(texts(edits.moveBullet(cv(), ref(0), -1))).toEqual(['one', 'two', 'three'])
    expect(texts(edits.moveBullet(cv(), ref(2), 3))).toEqual(['one', 'two', 'three'])
  })

  it('replaces and adds bullets', () => {
    const swapped = edits.replaceBullet(cv(), ref(1), { source: 'b9', text: 'nine', tech: null })
    expect(texts(swapped)).toEqual(['one', 'nine', 'three'])
    expect(swapped.sections[0].entries![0].bullets![1].source).toBe('b9')
    expect(texts(edits.addBullet(cv(), { section: 0, entry: 0 }, { source: 'b4', text: 'four' })))
      .toEqual(['one', 'two', 'three', 'four'])
  })

  it('moves entries within a section', () => {
    const two = edits.addBullet(cv(), { section: 0, entry: 0 }, { source: 'x', text: 'x' })
    two.sections[0].entries!.push({ source: 'job2', left: 'Intern', bullets: [] })
    expect(edits.moveEntry(two, { section: 0, entry: 1 }, 0).sections[0].entries!.map(e => e.source))
      .toEqual(['job2', 'job'])
  })

  it('records new unverified ids once', () => {
    const next = edits.addUnverified(edits.addUnverified(cv(), ['b2', 'b7']), ['b7'])
    expect(next.gap_report.unverified_used).toEqual(['b2', 'b7'])
  })

  it('lists the ids an entry already cites', () => {
    expect([...edits.citedIds(cv().sections[0].entries![0].bullets!)].sort()).toEqual(['b1', 'b2', 'b3'])
  })

  it('removes a bullet', () => {
    expect(texts(edits.removeBullet(cv(), ref(1)))).toEqual(['one', 'three'])
  })

  it('moves sections', () => {
    expect(edits.moveSection(cv(), 1, 0).sections.map(s => s.title)).toEqual(['Skills', 'Employment'])
  })

  it('removes a skill and drops empty groups', () => {
    const next = edits.removeSkill(cv(), 1, 1, 0)
    expect(next.sections[1].skills).toEqual([{ label: 'Frontend', items: ['React', 'Vite'] }])
  })

  it('toggles header extras without duplicates', () => {
    const on = edits.toggleHeaderExtra(edits.toggleHeaderExtra(cv(), 'UK', true), 'UK', true)
    expect(on.header_extras).toEqual(['UK'])
    expect(edits.toggleHeaderExtra(on, 'UK', false).header_extras).toEqual([])
  })

  it('hides and shows contact details without duplicates', () => {
    const hidden = edits.toggleContact(edits.toggleContact(cv(), 'github', false), 'github', false)
    expect(hidden.hide_contact).toEqual(['github'])
    expect(edits.toggleContact(hidden, 'github', true).hide_contact).toEqual([])
  })

  it('names the cover letter after the CV', () => {
    expect(edits.letterFilename('CV_Jordan_Avery_Systems')).toBe('Cover_Letter_Jordan_Avery_Systems')
    expect(edits.letterFilename('CV')).toBe('Cover_Letter')
    expect(edits.letterFilename('CVS_thing')).toBe('Cover_Letter_CVS_thing')
    expect(edits.letterFilename(undefined)).toBe('Cover_Letter')
  })

  it('finds unverified parts of merged sources', () => {
    expect(edits.unverifiedParts('b2+b3', ['b2'])).toEqual(['b2'])
    expect(edits.unverifiedParts('b1', ['b2'])).toEqual([])
  })
})

describe('errorFromBody', () => {
  it('reads the backend error shapes', () => {
    expect(errorFromBody(503, { detail: 'nope' }).message).toBe('nope')
    const rejected = errorFromBody(422, { detail: { error: 'draft_rejected', message: 'bad draft', problems: ['p1'] } })
    expect([rejected.message, rejected.problems]).toEqual(['bad draft', ['p1']])
    const invalid = errorFromBody(422, { detail: [{ loc: ['body', 'text'], msg: 'too short' }] })
    expect(invalid.problems).toEqual(['text: too short'])
  })
})

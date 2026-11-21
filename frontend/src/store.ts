import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  ApiError, api, type BankItem, type Extra, type ExtraKind, type JobAnalysis, type ProfileStatus, type TailorResult,
  type TailoredCV,
} from '@/api/client'
import * as edits from '@/lib/cv'
import { drafts } from '@/lib/drafts'
import { navigate } from '@/lib/route'

type Busy = null | 'analyse' | 'tailor' | 'export' | 'open' | 'extra' | 'rewrite' | 'letter'

interface State {
  applicationId: number | null // the tracker row this work belongs to (the URL says which: #/applications/42)
  versionId: number | null     // the saved CV version the editor started from
  jobText: string
  analysis: JobAnalysis | null
  result: TailorResult | null // coverage + header suggestions from the last tailoring run
  cv: TailoredCV | null       // the editable CV
  edited: boolean             // cv has changes not saved as a version (kept as a draft per application)
  extras: Extra[]             // cover letters etc. saved for this application, newest first
  bank: Record<string, BankItem[]> | null // profile bullets/facts by entry id, for swapping (not persisted)
  busy: Busy
  error: { message: string; problems: string[] } | null
  profile: ProfileStatus | null // whose profile.yaml the app is using (not persisted: asked on load)
  sampleChosen: boolean         // "explore with the sample profile" was picked, so don't show setup first


  setJobText: (text: string) => void
  analyse: () => Promise<void>
  tailor: () => Promise<void>
  exportPdf: () => Promise<void>
  /** Load an application (and a version of its CV, or its sent/newest one); unsaved edits come back from its draft. */
  openApplication: (id: number, versionId?: number | null) => Promise<boolean>
  /** The #/new page: an empty application, with any job text pasted there before. */
  startNew: () => void
  generateExtra: (kind: ExtraKind, recipient: string, notes: string) => Promise<void>
  /** Rewrite `current` (as edited) following `feedback`; the result is saved as a new text above it. */
  rewriteExtra: (kind: ExtraKind, current: string, feedback: string, recipient: string, notes: string) => Promise<void>
  downloadLetter: (text: string, subject: string | null) => Promise<void>
  saveExtra: (id: number, text: string, subject: string | null) => Promise<void>
  deleteExtra: (id: number) => Promise<void>
  loadBank: (force?: boolean) => Promise<void>
  loadProfileStatus: () => Promise<void>
  chooseSample: () => Promise<void>
  /** A new profile.yaml was saved: work tailored from the old one no longer matches it. */
  profileReplaced: (status: ProfileStatus) => void
  /** "New application": start over, dropping the pasted job text too. */
  reset: () => void
  clearError: () => void
  editCv: (fn: (cv: TailoredCV) => TailoredCV) => void
}

const empty = {
  applicationId: null, versionId: null, jobText: '', analysis: null, result: null, cv: null, edited: false,
  extras: [], bank: null, busy: null, error: null,
}

function toError(e: unknown) {
  return e instanceof ApiError ? { message: e.message, problems: e.problems } : { message: String(e), problems: [] }
}

function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  Object.assign(document.createElement('a'), { href: url, download: filename }).click()
  URL.revokeObjectURL(url)
}

export const useStore = create<State>()(persist((set, get) => {
  /** The tracker row for the current job, created on first use (also covers state saved before M5). */
  async function ensureApplication(): Promise<number> {
    const { applicationId, jobText, analysis } = get()
    if (applicationId != null) return applicationId
    if (!analysis) throw new Error('Analyse a job first')
    const created = await api.createApplication(jobText, analysis)
    set({ applicationId: created.id })
    return created.id
  }

  async function saveVersion(label: string, markSent = false) {
    const { cv, result } = get()
    if (!cv) return
    const id = await ensureApplication()
    const version = await api.addVersion(id, {
      label, cv, mark_sent: markSent,
      coverage: result?.coverage ?? [], header_extra_suggestions: result?.header_extra_suggestions ?? [],
    })
    // Saved: no draft needed, and the URL now points at this version (so a reload shows it).
    drafts.remove(id)
    set({ versionId: version.id, edited: false })
    navigate({ page: 'application', id, versionId: version.id }, { replace: true })
  }

  async function run(busy: Busy, fn: () => Promise<void>) {
    set({ busy, error: null })
    try {
      await fn()
    } catch (e) {
      set({ error: toError(e) })
    } finally {
      set({ busy: null })
    }
  }

  return {
    ...empty,
    jobText: drafts.loadNewJob(),
    profile: null,
    sampleChosen: false,

    setJobText: jobText => {
      set({ jobText })
      if (get().applicationId == null) drafts.saveNewJob(jobText)
    },

    analyse: () => run('analyse', async () => {
      const analysis = await api.analyse(get().jobText)
      set({ analysis, applicationId: null, versionId: null, result: null, cv: null, edited: false, extras: [] })
      const id = await ensureApplication() // every analysed job shows up in the tracker as a draft
      drafts.saveNewJob('')
      navigate({ page: 'application', id, versionId: null })
    }),

    tailor: () => run('tailor', async () => {
      const { analysis, cv } = get()
      if (!analysis) return
      const result = await api.tailor(analysis)
      // Keep header lines the user already ticked.
      set({ result, cv: { ...result.cv, header_extras: cv?.header_extras ?? [] } })
      await saveVersion('Tailored')
    }),

    exportPdf: () => run('export', async () => {
      const { cv } = get()
      if (!cv) return
      const blob = await api.pdf(cv) // fails on overflow, before anything is saved
      await saveVersion('Exported', true)
      download(blob, `${cv.filename}.pdf`)
    }),

    openApplication: async (id, versionId) => {
      let ok = false
      await run('open', async () => {
        const app = await api.getApplication(id)
        const vid = versionId ?? app.cv_version_id ?? app.versions[0]?.id ?? null
        const v = vid != null ? await api.getVersion(vid) : null
        const draft = drafts.load(id)
        const useDraft = draft !== null && (draft.versionId === null || draft.versionId === vid)
        set({
          applicationId: app.id, versionId: vid, jobText: app.job_text, analysis: app.analysis,
          result: v && { cv: v.cv, coverage: v.coverage, header_extra_suggestions: v.header_extra_suggestions },
          cv: useDraft ? draft.cv : v?.cv ?? null, edited: useDraft, extras: app.extras,
        })
        ok = true
      })
      return ok
    },

    generateExtra: (kind, recipient, notes) => run('extra', async () => {
      const { analysis, cv } = get()
      if (!analysis) return
      const extra = await api.generateExtra({
        kind, job: analysis, cv, recipient: recipient || null, notes: notes || null,
        application_id: await ensureApplication(),
      })
      set({ extras: [extra, ...get().extras] })
    }),

    rewriteExtra: (kind, current, feedback, recipient, notes) => run('rewrite', async () => {
      const { analysis, cv } = get()
      if (!analysis) return
      const extra = await api.generateExtra({
        kind, job: analysis, cv, recipient: recipient || null, notes: notes || null,
        previous: current, feedback: feedback || null, application_id: await ensureApplication(),
      })
      set({ extras: [extra, ...get().extras] })
    }),

    downloadLetter: (text, subject) => run('letter', async () => {
      const { cv } = get()
      const filename = edits.letterFilename(cv?.filename)
      const blob = await api.letterPdf({
        text, subject, filename, hide_contact: cv?.hide_contact ?? [], header_extras: cv?.header_extras ?? [],
      })
      download(blob, `${filename}.pdf`)
    }),

    saveExtra: async (id, text, subject) => {
      const saved = await api.updateExtra(id, text, subject)
      set({ extras: get().extras.map(e => (e.id === id ? saved : e)) })
    },

    deleteExtra: async id => {
      await api.deleteExtra(id)
      set({ extras: get().extras.filter(e => e.id !== id) })
    },

    loadBank: async force => {
      if (get().bank && !force) return
      try {
        set({ bank: await api.bank() })
      } catch (e) {
        set({ error: toError(e) })
      }
    },

    loadProfileStatus: async () => {
      try {
        set({ profile: await api.profileStatus() })
      } catch (e) {
        set({ error: toError(e) })
      }
    },

    chooseSample: async () => {
      try {
        set({ profile: await api.useExampleProfile(), sampleChosen: true })
      } catch (e) {
        set({ error: toError(e) })
      }
    },

    profileReplaced: status => set({ ...empty, profile: status, sampleChosen: false }),

    startNew: () => set({ ...empty, jobText: drafts.loadNewJob(), bank: get().bank }),

    reset: () => {
      drafts.saveNewJob('')
      set({ ...empty, bank: get().bank })
    },
    clearError: () => set({ error: null }),
    editCv: fn => {
      const { cv, applicationId, versionId } = get()
      if (!cv) return
      const next = fn(cv)
      set({ cv: next, edited: true })
      if (applicationId != null) drafts.save(applicationId, { versionId, cv: next })
    },
  }
}, {
  name: 'cv-tailor',
  // Shared by every tab, so only app-wide settings live here. Which application is open is in the URL;
  // unsaved edits are drafts per application (lib/drafts.ts).
  version: 1,
  partialize: ({ sampleChosen }) => ({ sampleChosen }),
  migrate: (old, version) => {
    // Before v1 the open application lived here too. It's dropped, not turned into a draft: the saved state
    // may come from another copy of the app on the same address, whose application ids mean something else.
    // A pasted job that wasn't analysed yet is kept.
    const o = (old ?? {}) as Partial<State>
    if (version < 1 && o.applicationId == null && o.jobText) drafts.saveNewJob(o.jobText)
    return { sampleChosen: o.sampleChosen ?? false } as State
  },
}))

export { edits }

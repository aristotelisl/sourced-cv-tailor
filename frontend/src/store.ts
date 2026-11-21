import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  ApiError, api, type BankItem, type Extra, type ExtraKind, type JobAnalysis, type ProfileStatus, type TailorResult,
  type TailoredCV,
} from '@/api/client'
import * as edits from '@/lib/cv'

type Busy = null | 'analyse' | 'tailor' | 'export' | 'open' | 'extra' | 'rewrite' | 'letter'

interface State {
  applicationId: number | null // the tracker row this work belongs to
  jobText: string
  analysis: JobAnalysis | null
  result: TailorResult | null // coverage + header suggestions from the last tailoring run
  cv: TailoredCV | null       // the editable CV
  edited: boolean             // cv differs from what tailoring returned
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
  openApplication: (id: number, versionId?: number | null) => Promise<boolean>
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
  reset: () => void
  clearError: () => void
  editCv: (fn: (cv: TailoredCV) => TailoredCV) => void
}

const empty = {
  applicationId: null, jobText: '', analysis: null, result: null, cv: null, edited: false, extras: [],
  bank: null, busy: null, error: null,
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
    await api.addVersion(await ensureApplication(), {
      label, cv, mark_sent: markSent,
      coverage: result?.coverage ?? [], header_extra_suggestions: result?.header_extra_suggestions ?? [],
    })
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
    profile: null,
    sampleChosen: false,

    setJobText: jobText => set({ jobText }),

    analyse: () => run('analyse', async () => {
      const analysis = await api.analyse(get().jobText)
      set({ analysis, applicationId: null, result: null, cv: null, edited: false, extras: [] })
      await ensureApplication() // every analysed job shows up in the tracker as a draft
    }),

    tailor: () => run('tailor', async () => {
      const { analysis, cv } = get()
      if (!analysis) return
      const result = await api.tailor(analysis)
      // Keep header lines the user already ticked.
      set({ result, cv: { ...result.cv, header_extras: cv?.header_extras ?? [] }, edited: false })
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
        set({
          applicationId: app.id, jobText: app.job_text, analysis: app.analysis, edited: false,
          result: v && { cv: v.cv, coverage: v.coverage, header_extra_suggestions: v.header_extra_suggestions },
          cv: v?.cv ?? null, extras: app.extras,
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

    reset: () => set({ ...empty, bank: get().bank }),
    clearError: () => set({ error: null }),
    editCv: fn => {
      const { cv } = get()
      if (cv) set({ cv: fn(cv), edited: true })
    },
  }
}, {
  name: 'cv-tailor',
  // Tailoring costs a minute and a few cents: keep the work across reloads, but not transient state.
  partialize: ({ applicationId, jobText, analysis, result, cv, edited, extras, sampleChosen }) =>
    ({ applicationId, jobText, analysis, result, cv, edited, extras, sampleChosen }),
}))

export { edits }

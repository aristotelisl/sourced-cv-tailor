import type { TailoredCV } from '@/api/client'

/**
 * Unsaved work, kept in localStorage so a reload doesn't lose it. One entry per application
 * (not one for the whole app), so two tabs on different applications never overwrite each other.
 */
export interface Draft {
  versionId: number | null // the CV version the edits started from (null: whichever opens first)
  cv: TailoredCV
}

const draftKey = (applicationId: number) => `cv-tailor:draft:${applicationId}`
const NEW_JOB = 'cv-tailor:new-job' // a job listing pasted but not analysed yet

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : null
  } catch {
    return null
  }
}

function write(key: string, value: unknown) {
  try {
    if (value == null) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // storage full or disabled: drafts are a convenience, never block the app
  }
}

export const drafts = {
  load: (applicationId: number) => read<Draft>(draftKey(applicationId)),
  save: (applicationId: number, draft: Draft) => write(draftKey(applicationId), draft),
  remove: (applicationId: number) => write(draftKey(applicationId), null),
  loadNewJob: () => read<string>(NEW_JOB) ?? '',
  saveNewJob: (text: string) => write(NEW_JOB, text || null),
}

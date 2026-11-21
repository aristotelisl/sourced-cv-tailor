// Typed wrappers around the backend. Types come from src/api/schema.ts (generated: npm run gen:types).
import type { components } from './schema'

type S = components['schemas']
export type TailoredCV = S['TailoredCV']
export type Section = S['Section']
export type Entry = S['Entry']
export type Bullet = S['Bullet']
export type JobAnalysis = S['JobAnalysis']
export type TailorResult = S['TailorResult']
export type RequirementCoverage = S['RequirementCoverage']
export type FitCheck = S['FitCheck']
export type ProfileSummary = S['ProfileSummary']
export type ApplicationSummary = S['ApplicationSummary']
export type ApplicationDetail = S['ApplicationDetail']
export type ApplicationUpdate = S['ApplicationUpdate']
export type ApplicationStatus = S['ApplicationSummary']['status']
export type CvVersion = S['CvVersion']
export type CvVersionCreate = S['CvVersionCreate']
export type Extra = S['Extra']
export type ExtraKind = S['Extra']['kind']
export type ExtraRequest = S['ExtraRequest']
export type LetterPdfRequest = S['LetterPdfRequest']
export type BulletRequest = S['BulletRequest']
export type BulletOption = S['BulletOption']
export type BankItem = S['BankItem']
export type ProfileProposal = S['ProfileProposal']
export type ProfileStatus = S['ProfileStatus']
export type ProfileImportRequest = S['ProfileImportRequest']
export type ProfileImportResult = S['ProfileImportResult']
export type ProfileSaveResult = S['ProfileSaveResult']

export class ApiError extends Error {
  readonly problems: string[]
  constructor(message: string, problems: string[] = []) {
    super(message)
    this.problems = problems
  }
}

/** FastAPI errors come as {detail: string}, {detail: {message, problems?}} or {detail: [validation errors]}. */
export function errorFromBody(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return new ApiError(detail)
  if (Array.isArray(detail)) {
    const msgs = detail.map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join('.')}: ${d.msg}`)
    return new ApiError(`Invalid request (${status})`, msgs)
  }
  if (detail && typeof detail === 'object') {
    const d = detail as { message?: string; problems?: string[] }
    return new ApiError(d.message ?? `Request failed (${status})`, d.problems ?? [])
  }
  return new ApiError(`Request failed (${status})`)
}

async function request(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(path, {
    ...init,
    headers: init.body ? { 'Content-Type': 'application/json', ...init.headers } : init.headers,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw errorFromBody(res.status, body)
  }
  return res
}

const post = (path: string, body: unknown, signal?: AbortSignal) =>
  request(path, { method: 'POST', body: JSON.stringify(body), signal })

export const api = {
  profile: async (): Promise<ProfileSummary> => (await request('/api/profile')).json(),
  analyse: async (text: string): Promise<JobAnalysis> => (await post('/api/analyse', { text })).json(),
  tailor: async (job: JobAnalysis, header_extras: string[] = []): Promise<TailorResult> =>
    (await post('/api/tailor', { job, header_extras })).json(),
  renderHtml: async (cv: TailoredCV, signal?: AbortSignal): Promise<string> =>
    (await post('/api/render/html', cv, signal)).text(),
  checkFit: async (cv: TailoredCV, signal?: AbortSignal): Promise<FitCheck> =>
    (await post('/api/render/check', cv, signal)).json(),
  pdf: async (cv: TailoredCV): Promise<Blob> => (await post('/api/render/pdf', cv)).blob(),
  rewriteBullet: async (req: BulletRequest): Promise<BulletOption[]> =>
    (await (await post('/api/tailor/bullet', req)).json()).options,

  // Profile setup (first run): read a CV into a proposed profile.yaml, or explore with the sample
  profileStatus: async (): Promise<ProfileStatus> => (await request('/api/profile/status')).json(),
  useExampleProfile: async (): Promise<ProfileStatus> => (await post('/api/profile/use-example', {})).json(),
  importCv: async (req: ProfileImportRequest): Promise<ProfileImportResult> =>
    (await post('/api/profile/import', req)).json(),
  saveProfile: async (yaml: string): Promise<ProfileSaveResult> => (await post('/api/profile/save', { yaml })).json(),

  // Profile: the bullet bank, and answering gap-report questions into profile.yaml
  bank: async (): Promise<Record<string, BankItem[]>> => (await request('/api/profile/bank')).json(),
  answerQuestion: async (question: string, answer: string, job: JobAnalysis | null): Promise<ProfileProposal> =>
    (await post('/api/profile/answer', { question, answer, job })).json(),
  applyProfileEdits: async (question: string, answer: string, proposal: ProfileProposal): Promise<void> => {
    await post('/api/profile/apply', { question, answer, edits: proposal.edits, base: proposal.base })
  },

  // Tracker
  listApplications: async (): Promise<ApplicationSummary[]> => (await request('/api/applications')).json(),
  createApplication: async (job_text: string, analysis: JobAnalysis): Promise<ApplicationDetail> =>
    (await post('/api/applications', { job_text, analysis })).json(),
  getApplication: async (id: number): Promise<ApplicationDetail> => (await request(`/api/applications/${id}`)).json(),
  updateApplication: async (id: number, update: ApplicationUpdate): Promise<ApplicationDetail> =>
    (await request(`/api/applications/${id}`, { method: 'PATCH', body: JSON.stringify(update) })).json(),
  deleteApplication: async (id: number): Promise<void> => {
    await request(`/api/applications/${id}`, { method: 'DELETE' })
  },
  addVersion: async (applicationId: number, version: CvVersionCreate): Promise<CvVersion> =>
    (await post(`/api/applications/${applicationId}/versions`, version)).json(),
  getVersion: async (id: number): Promise<CvVersion> => (await request(`/api/versions/${id}`)).json(),
  versionPdfUrl: (id: number) => `/api/versions/${id}/pdf`,

  // Extras (cover letter, about me, messages)
  generateExtra: async (req: ExtraRequest): Promise<Extra> => (await post('/api/extras', req)).json(),
  updateExtra: async (id: number, text: string, subject: string | null): Promise<Extra> =>
    (await request(`/api/extras/${id}`, { method: 'PUT', body: JSON.stringify({ text, subject }) })).json(),
  letterPdf: async (req: LetterPdfRequest): Promise<Blob> => (await post('/api/extras/letter-pdf', req)).blob(),
  deleteExtra: async (id: number): Promise<void> => {
    await request(`/api/extras/${id}`, { method: 'DELETE' })
  },
}

export const STATUSES: ApplicationStatus[] = ['draft', 'applied', 'interview', 'offer', 'rejected', 'on-hold']

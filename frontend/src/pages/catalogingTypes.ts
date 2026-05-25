export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface ChapterItem {
  id: string
  title: string
  word_count: number
}

export type CatalogingMode = 'auto' | 'manual'

export interface CatalogingJob {
  id: string
  project_id: string
  status: string
  execution_mode: CatalogingMode
  current_chapter_id?: string | null
  blocked_chapter_id?: string | null
  total_chapters: number
  completed_chapters: number
  failed_chapters: number
  error?: string | null
  created_at?: string | null
  updated_at?: string | null
  completed_at?: string | null
}

export interface CatalogingRun {
  id: string
  chapter_id: string
  chapter_title: string
  status: string
  chapter_order: number
  error?: string | null
}

export interface CatalogingCandidate {
  id: string
  chapter_id: string
  item_type: string
  chapter_run_id: string
  target_name?: string | null
  payload: Record<string, unknown>
  status: string
  confidence?: number | null
  evidence?: string | null
  error?: string | null
}

export const catalogingStatusColor: Record<string, string> = {
  queued: 'default',
  running: 'processing',
  waiting_confirmation: 'orange',
  paused_on_failure: 'red',
  paused: 'orange',
  completed: 'green',
  failed: 'red',
  pending: 'default',
  edited: 'blue',
  approved: 'green',
  rejected: 'red',
  applying: 'processing',
  applied: 'green',
  apply_failed: 'red',
}

export function safeStringify(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}

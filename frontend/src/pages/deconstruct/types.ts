/* Shared types for the deconstruct page. */

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface ChapterOpt {
  id: string
  title: string
  word_count: number
  preview: string
}

export interface PreviewData {
  chapters: ChapterOpt[]
  total_chapters: number
  total_words: number
  can_deconstruct: boolean
  combined_text: string
}

export interface PlotNode {
  description: string
  type: string
  position_pct: number
  importance: string
}

export interface DeconCharacter {
  name: string
  role: string
  role_type?: string
  mention_count: number
  importance: string
  appearance?: string
  appearance_source?: string
  personality?: string
  background?: string
  abilities?: string[]
  arc_description: string
  motivation?: string
  conflict?: string
  speech_style?: string
  relationship_network?: Array<{
    target_name: string
    relationship_type: string
    description?: string
    attitude?: string
  }>
  relationships?: Array<{
    target_name: string
    relationship_type: string
    description?: string
  }>
  appearance_records?: Array<{
    chapter_title?: string
    scene?: string
    role_in_scene?: string
    summary?: string
  }>
  ai_config?: {
    custom_system_prompt?: string
    tone_style?: string
    catchphrases?: string[]
    emotion_tendency?: string
  }
}

export interface Highlight {
  type: string
  description: string
  position_pct: number
  intensity: string
}

export interface RhythmPoint {
  position_pct: number
  pace: string
  label: string
}

export interface Pattern {
  type: string
  description: string
  frequency: string
  examples: string[]
}

export interface GoldenThree {
  hook?: string
  protagonist_goal?: string
  core_conflict?: string
  reader_expectation?: string
  chapter_1_function?: string
  chapter_2_function?: string
  chapter_3_function?: string
  problems?: string[]
  optimization_suggestions?: string[]
}

export interface WorldbuildingEntryResult {
  dimension: string
  title: string
  content: string
  related_characters?: string[]
  plot_usage?: string
  constraints?: string[]
}

export interface ChunkProgress {
  index: number
  status: 'pending' | 'completed' | 'failed' | string
  summary?: string
  characters?: string[]
  events?: string[]
  highlights?: string[]
  pacing?: string
  narrative_mode?: string
  error?: string
  streaming?: boolean
  stream_text?: string
  raw?: Record<string, unknown>
}

export interface ProgressLog {
  time: string
  level: 'info' | 'warning' | 'error' | string
  message: string
}

export interface DeconstructReport {
  id: string
  title: string
  status: 'queued' | 'processing' | 'completed' | 'failed' | string
  phase: 'queued' | 'map' | 'reduce' | 'completed' | 'failed' | string
  structure?: {
    volumes?: Array<{
      title: string
      summary?: string
      chapters?: Array<{
        title: string
        summary: string
        goal?: string
        conflict?: string
        outcome?: string
        hook?: string
        characters?: string[]
        character_roles?: Array<{ name: string; role_in_scene?: string }>
      }>
    }>
    total_estimated_chapters?: number
  }
  golden_three?: GoldenThree | null
  plot_nodes?: PlotNode[]
  characters?: DeconCharacter[]
  worldbuilding_entries?: WorldbuildingEntryResult[]
  highlights?: Highlight[]
  rhythm_curve?: RhythmPoint[] | null
  patterns?: Pattern[] | null
  reduce_sections?: string[]
  reduce_errors?: Record<string, string>
  chunk_results?: ChunkProgress[]
  logs?: ProgressLog[]
  total_chunks: number
  completed_chunks: number
  failed_chunks: number
  elapsed_seconds?: number
  avg_seconds_per_chunk?: number
  estimated_remaining_seconds?: number
  map_concurrency?: number
  map_model?: string
  reduce_model?: string
  analysis_mode?: 'fast' | 'detailed' | string
  total_words: number
  reduce_error?: string
  error?: string
  created_at: string
  completed_at?: string
}

export interface ReportSummary {
  id: string
  title: string
  status: string
  phase?: string
  total_chunks?: number
  completed_chunks?: number
  failed_chunks?: number
  total_words?: number
  created_at?: string
  completed_at?: string
}

export interface DeconstructPageProps {
  projectId: string
}

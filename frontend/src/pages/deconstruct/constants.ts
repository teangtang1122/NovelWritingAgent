/* Constants and pure helper functions for the deconstruct page. */
import type { DeconstructReport } from './types'

export const PLOT_TYPE_LABEL: Record<string, string> = {
  intro: '引入',
  development: '发展',
  turn: '转折',
  climax: '高潮',
  resolution: '收尾',
}

export const PLOT_TYPE_COLOR: Record<string, string> = {
  intro: 'blue',
  development: 'green',
  turn: 'orange',
  climax: 'red',
  resolution: 'purple',
}

export const IMPORTANCE_COLOR: Record<string, string> = {
  high: 'red',
  medium: 'orange',
  low: 'default',
}

export const INTENSITY_COLOR: Record<string, string> = {
  high: '#f5222d',
  medium: '#fa8c16',
  low: '#52c41a',
}

export const phaseLabel = (phase?: string) => {
  const labels: Record<string, string> = {
    queued: '等待开始',
    map: '分块分析',
    reduce: '自动合并',
    completed: '已完成',
    failed: '失败',
  }
  return labels[phase || ''] || phase || '未开始'
}

export const reportPercent = (report?: DeconstructReport | null) => {
  if (!report) return 0
  if (report.status === 'completed') return 100
  if (report.phase === 'reduce') return 95
  if (!report.total_chunks) return 0
  return Math.min(90, Math.floor((report.completed_chunks / report.total_chunks) * 90))
}

export const formatSeconds = (seconds?: number) => {
  if (!seconds || seconds <= 0) return '0秒'
  if (seconds < 60) return `${Math.round(seconds)}秒`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return rest ? `${minutes}分${rest}秒` : `${minutes}分`
}

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Col, Row, message } from 'antd'
import { apiClient } from '../api/client'
import CatalogingCandidatesPanel from './CatalogingCandidatesPanel'
import CatalogingHeader from './CatalogingHeader'
import CatalogingJobControlCard from './CatalogingJobControlCard'
import CatalogingSidebar from './CatalogingSidebar'
import type {
  ApiResponse,
  CatalogingCandidate,
  CatalogingJob,
  CatalogingMode,
  CatalogingRun,
  ChapterItem,
} from './catalogingTypes'
import { safeStringify } from './catalogingTypes'

interface CatalogingPageProps {
  projectId: string
}

function CatalogingPage({ projectId }: CatalogingPageProps) {
  const [mode, setMode] = useState<CatalogingMode>('auto')
  const [chapters, setChapters] = useState<ChapterItem[]>([])
  const [selectedChapterIds, setSelectedChapterIds] = useState<string[]>([])
  const [jobs, setJobs] = useState<CatalogingJob[]>([])
  const [job, setJob] = useState<CatalogingJob | null>(null)
  const [runs, setRuns] = useState<CatalogingRun[]>([])
  const [candidates, setCandidates] = useState<CatalogingCandidate[]>([])
  const [candidateDrafts, setCandidateDrafts] = useState<Record<string, string>>({})
  const [candidateStatusFilter, setCandidateStatusFilter] = useState<string>('all')
  const [newCandidateType, setNewCandidateType] = useState<string>('chapter_summary')
  const [newCandidatePayload, setNewCandidatePayload] = useState<string>('{\n  "summary_text": ""\n}')
  const [logs, setLogs] = useState<string[]>([])
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(false)

  const progress = useMemo(() => {
    if (!job || !job.total_chapters) return 0
    return Math.round(((job.completed_chapters || 0) / job.total_chapters) * 100)
  }, [job])

  const visibleCandidates = useMemo(() => {
    if (candidateStatusFilter === 'all') return candidates
    return candidates.filter((item) => item.status === candidateStatusFilter)
  }, [candidateStatusFilter, candidates])

  const appendLog = useCallback((text: string) => {
    setLogs((current) => [text, ...current].slice(0, 80))
  }, [])

  const fetchChapters = useCallback(async () => {
    const res = await apiClient.get<ApiResponse<{ items: ChapterItem[]; total: number }>>(`/projects/${projectId}/chapters`)
    const items = res.data.data.items || []
    setChapters(items)
    setSelectedChapterIds(items.map((item) => item.id))
  }, [projectId])

  const fetchJobs = useCallback(async () => {
    const res = await apiClient.get<ApiResponse<{ items: CatalogingJob[]; total: number }>>(`/projects/${projectId}/cataloging/jobs`)
    setJobs(res.data.data.items || [])
  }, [projectId])

  const fetchJob = useCallback(async (jobId: string) => {
    const res = await apiClient.get<ApiResponse<{ job: CatalogingJob; runs: CatalogingRun[] }>>(`/projects/${projectId}/cataloging/${jobId}`)
    setJob(res.data.data.job)
    setMode(res.data.data.job.execution_mode)
    setRuns(res.data.data.runs)
  }, [projectId])

  const fetchCandidates = useCallback(async (jobId: string) => {
    const res = await apiClient.get<ApiResponse<{ items: CatalogingCandidate[]; total: number }>>(`/projects/${projectId}/cataloging/${jobId}/candidates`)
    setCandidates(res.data.data.items)
    setCandidateDrafts((current) => {
      const next = { ...current }
      res.data.data.items.forEach((item) => {
        if (!next[item.id]) next[item.id] = safeStringify(item.payload)
      })
      return next
    })
  }, [projectId])

  const loadJob = useCallback(async (jobId: string) => {
    await fetchJob(jobId)
    await fetchCandidates(jobId)
  }, [fetchCandidates, fetchJob])

  const handleStreamEvent = useCallback((raw: string) => {
    let event: any
    try {
      event = JSON.parse(raw)
    } catch {
      return
    }

    if (event.job) setJob(event.job)
    if (event.run) {
      setRuns((current) => {
        const idx = current.findIndex((item) => item.id === event.run.id)
        if (idx < 0) return [...current, event.run].sort((a, b) => a.chapter_order - b.chapter_order)
        const next = [...current]
        next[idx] = event.run
        return next
      })
    }
    if (event.candidate) {
      setCandidates((current) => {
        const idx = current.findIndex((item) => item.id === event.candidate.id)
        if (idx < 0) return [...current, event.candidate]
        const next = [...current]
        next[idx] = event.candidate
        return next
      })
      setCandidateDrafts((current) => ({
        ...current,
        [event.candidate.id]: current[event.candidate.id] || safeStringify(event.candidate.payload),
      }))
    }

    const label = event.message || event.detail || event.error || event.type
    if (label) appendLog(`${new Date().toLocaleTimeString()} ${label}`)
    if (['completed', 'paused_on_failure', 'waiting_confirmation', 'paused', 'cancelled'].includes(event.type)) {
      setStreaming(false)
      fetchJobs().catch(() => undefined)
    }
  }, [appendLog, fetchJobs])

  const streamJob = useCallback((jobId: string) => {
    setStreaming(true)
    apiClient.stream(
      `/projects/${projectId}/cataloging/${jobId}/stream`,
      {},
      handleStreamEvent,
      (err) => {
        setStreaming(false)
        message.error(err.message || '作品建档流式连接失败')
      },
    )
  }, [handleStreamEvent, projectId])

  const startJob = async () => {
    if (selectedChapterIds.length === 0) {
      message.warning('请至少选择一个章节')
      return
    }
    setLoading(true)
    try {
      const res = await apiClient.post<ApiResponse<CatalogingJob>>(`/projects/${projectId}/cataloging/start`, {
        execution_mode: mode,
        chapter_ids: selectedChapterIds,
      })
      setJob(res.data.data)
      setCandidates([])
      setCandidateDrafts({})
      setRuns([])
      setLogs([])
      appendLog('作品建档任务已创建')
      fetchJobs().catch(() => undefined)
      streamJob(res.data.data.id)
    } catch (err: any) {
      message.error(err.message || '启动失败')
    } finally {
      setLoading(false)
    }
  }

  const updateMode = async (nextMode: CatalogingMode) => {
    setMode(nextMode)
    if (!job) return
    const res = await apiClient.patch<ApiResponse<{ job: CatalogingJob; should_resume: boolean }>>(`/projects/${projectId}/cataloging/${job.id}/mode`, {
      execution_mode: nextMode,
    })
    setJob(res.data.data.job)
    appendLog(`已切换为${nextMode === 'auto' ? '自动' : '手动确认'}模式`)
    if (res.data.data.should_resume && !streaming) {
      streamJob(job.id)
    }
  }

  const saveCandidate = async (candidate: CatalogingCandidate, status?: string) => {
    try {
      const parsed = JSON.parse(candidateDrafts[candidate.id] || '{}')
      const res = await apiClient.patch<ApiResponse<CatalogingCandidate>>(`/projects/${projectId}/cataloging/candidates/${candidate.id}`, {
        payload: parsed,
        status,
      })
      setCandidates((current) => current.map((item) => item.id === candidate.id ? res.data.data : item))
      message.success('候选项已更新')
    } catch (err: any) {
      message.error(err.message || '候选项 JSON 不合法')
    }
  }

  const applyPending = async () => {
    if (!job) return
    setLoading(true)
    try {
      await apiClient.post<ApiResponse<unknown>>(`/projects/${projectId}/cataloging/${job.id}/apply-pending`)
      await fetchJob(job.id)
      await fetchCandidates(job.id)
      streamJob(job.id)
    } catch (err: any) {
      message.error(err.message || '写入失败')
    } finally {
      setLoading(false)
    }
  }

  const bulkUpdateCandidates = async (status: 'approved' | 'rejected') => {
    if (!job) return
    try {
      const editableIds = visibleCandidates
        .filter((item) => !['applying', 'applied'].includes(item.status))
        .map((item) => item.id)
      const res = await apiClient.patch<ApiResponse<{ items: CatalogingCandidate[]; total: number }>>(`/projects/${projectId}/cataloging/${job.id}/candidates/bulk`, {
        candidate_ids: editableIds,
        status,
      })
      const byId = new Map(res.data.data.items.map((item) => [item.id, item]))
      setCandidates((current) => current.map((item) => byId.get(item.id) || item))
      message.success(status === 'approved' ? '已批量确认候选项' : '已批量拒绝候选项')
    } catch (err: any) {
      message.error(err.message || '批量更新失败')
    }
  }

  const retryCurrent = async () => {
    if (!job) return
    setLoading(true)
    try {
      await apiClient.post<ApiResponse<unknown>>(`/projects/${projectId}/cataloging/${job.id}/retry-current`)
      await fetchJob(job.id)
      await fetchCandidates(job.id)
      streamJob(job.id)
    } catch (err: any) {
      message.error(err.message || '重试失败')
    } finally {
      setLoading(false)
    }
  }

  const recoverCurrent = async () => {
    if (!job) return
    setLoading(true)
    try {
      await apiClient.post<ApiResponse<unknown>>(`/projects/${projectId}/cataloging/${job.id}/recover-current`)
      await fetchJob(job.id)
      await fetchCandidates(job.id)
      message.success('当前章节已转入人工确认')
    } catch (err: any) {
      message.error(err.message || '转入人工确认失败')
    } finally {
      setLoading(false)
    }
  }

  const createManualCandidate = async () => {
    if (!job) return
    try {
      const parsed = JSON.parse(newCandidatePayload || '{}')
      const res = await apiClient.post<ApiResponse<CatalogingCandidate>>(`/projects/${projectId}/cataloging/${job.id}/candidates`, {
        item_type: newCandidateType,
        payload: parsed,
        status: 'edited',
      })
      const candidate = res.data.data
      setCandidates((current) => [...current, candidate])
      setCandidateDrafts((current) => ({ ...current, [candidate.id]: safeStringify(candidate.payload) }))
      message.success('候选项已新增')
    } catch (err: any) {
      message.error(err.message || '新增候选项失败')
    }
  }

  const pauseCurrentJob = async () => {
    if (!job) return
    try {
      const res = await apiClient.post<ApiResponse<{ job: CatalogingJob }>>(`/projects/${projectId}/cataloging/${job.id}/pause`)
      setJob(res.data.data.job)
      setStreaming(false)
      await fetchJobs()
    } catch (err: any) {
      message.error(err.message || '暂停失败')
    }
  }

  const resumeCurrentJob = async () => {
    if (!job) return
    try {
      const res = await apiClient.post<ApiResponse<{ job: CatalogingJob }>>(`/projects/${projectId}/cataloging/${job.id}/resume`)
      setJob(res.data.data.job)
      await fetchJobs()
      streamJob(job.id)
    } catch (err: any) {
      message.error(err.message || '继续失败')
    }
  }

  const cancelCurrentJob = async () => {
    if (!job) return
    try {
      const res = await apiClient.post<ApiResponse<{ job: CatalogingJob }>>(`/projects/${projectId}/cataloging/${job.id}/cancel`)
      setJob(res.data.data.job)
      setStreaming(false)
      await fetchJobs()
    } catch (err: any) {
      message.error(err.message || '取消失败')
    }
  }

  const skipCurrent = async () => {
    if (!job) return
    await apiClient.post<ApiResponse<unknown>>(`/projects/${projectId}/cataloging/${job.id}/skip-current`)
    await fetchJob(job.id)
    await fetchJobs()
    streamJob(job.id)
  }

  const updateCandidateDraft = (candidateId: string, value: string) => {
    setCandidateDrafts((current) => ({ ...current, [candidateId]: value }))
  }

  useEffect(() => {
    fetchChapters().catch((err) => message.error(err.message || '获取章节失败'))
    fetchJobs().catch(() => undefined)
  }, [fetchChapters, fetchJobs])

  return (
    <div>
      <CatalogingHeader
        mode={mode}
        loading={loading}
        streaming={streaming}
        onModeChange={updateMode}
        onRefreshChapters={fetchChapters}
        onStartJob={startJob}
      />

      <CatalogingJobControlCard
        job={job}
        progress={progress}
        streaming={streaming}
        onApplyPending={applyPending}
        onRetryCurrent={retryCurrent}
        onRecoverCurrent={recoverCurrent}
        onSkipCurrent={skipCurrent}
        onPauseCurrentJob={pauseCurrentJob}
        onCancelCurrentJob={cancelCurrentJob}
        onResumeCurrentJob={resumeCurrentJob}
        onStreamJob={streamJob}
      />

      <Row gutter={16}>
        <Col span={6}>
          <CatalogingSidebar
            chapters={chapters}
            selectedChapterIds={selectedChapterIds}
            jobs={jobs}
            activeJob={job}
            runs={runs}
            onSelectedChapterIdsChange={setSelectedChapterIds}
            onLoadJob={loadJob}
          />
        </Col>
        <Col span={18}>
          <CatalogingCandidatesPanel
            job={job}
            visibleCandidates={visibleCandidates}
            candidateDrafts={candidateDrafts}
            candidateStatusFilter={candidateStatusFilter}
            newCandidateType={newCandidateType}
            newCandidatePayload={newCandidatePayload}
            logs={logs}
            onCandidateStatusFilterChange={setCandidateStatusFilter}
            onNewCandidateTypeChange={setNewCandidateType}
            onNewCandidatePayloadChange={setNewCandidatePayload}
            onBulkUpdateCandidates={bulkUpdateCandidates}
            onSaveCandidate={saveCandidate}
            onCandidateDraftChange={updateCandidateDraft}
            onCreateManualCandidate={createManualCandidate}
          />
        </Col>
      </Row>
    </div>
  )
}

export default CatalogingPage

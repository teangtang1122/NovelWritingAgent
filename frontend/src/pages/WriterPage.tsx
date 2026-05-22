import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Alert,
  Button,
  Empty,
  Form,
  Input,
  List,
  Popconfirm,
  Select,
  Slider,
  Space,
  Switch,
  Tag,
  Tabs,
  Timeline,
  Typography,
  message,
} from 'antd'
import {
  DeleteOutlined,
  DiffOutlined,
  FileTextOutlined,
  HistoryOutlined,
  PlusOutlined,
  ReloadOutlined,
  RobotOutlined,
  RollbackOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
  StopOutlined,
  UserOutlined,
  TeamOutlined,
  EditOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { apiClient } from '../api/client'
import WorkspaceAssistantChat from '../components/WorkspaceAssistantChat'
import { useModelOptions } from '../hooks/useModelOptions'
import './WriterPage.css'

const { Paragraph, Text, Title } = Typography
const { TextArea } = Input

const DEFAULT_FORBIDDEN_SENTENCE_PATTERNS = [
  '不是……是……',
  '不是……而是……',
  '不是……却是……',
  '与其说……不如说……',
].join('\n')

const DEFAULT_RHETORIC_GUIDELINES = '克制使用比喻、拟人、排比等修辞，禁止连续堆叠比喻。优先用具体动作、感官细节、因果推进和角色反应来表达画面与情绪。非必要不使用抽象概念比喻；同一段落不要出现多个比喻。'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface ChapterItem {
  id: string
  project_id: string
  outline_node_id?: string | null
  title: string
  word_count: number
  current_version: number
  outline_title?: string | null
  outline_status?: string | null
  outline_node_type?: string | null
  outline_path: string[]
  summary_text?: string | null
  key_events?: string[]
  created_at: string
  updated_at: string
}

interface ChapterDetail extends ChapterItem {
  content: string
  snapshot_count: number
}

interface SnapshotItem {
  id: string
  chapter_id: string
  version_number: number
  word_count: number
  trigger_type: string
  created_at: string
}

interface OutlineNode {
  id: string
  parent_id?: string | null
  node_type: 'volume' | 'chapter' | 'section'
  title: string
  status: string
  sort_order: number
  children: OutlineNode[]
}

interface CharacterItem {
  id: string
  name: string
  role_type?: string
}

interface DiffChange {
  type: 'equal' | 'replace' | 'delete' | 'insert'
  from_start: number
  from_end: number
  to_start: number
  to_end: number
  from_lines: string[]
  to_lines: string[]
}

interface DiffResponse {
  from_snapshot: SnapshotItem
  to_snapshot: SnapshotItem
  changes: DiffChange[]
  total_changes: number
}

interface ChapterFormValues {
  title: string
  outline_node_id?: string
  content: string
}

type AIMode = 'assistant' | 'narrator' | 'character' | 'battle' | 'conflict'

interface ConflictItem {
  type: string
  title: string
  description: string
  involved_characters: string[]
  tension_level: string
  suggested_outcome: string
}

interface ChangeLogItem {
  id: string
  character_id: string
  character_name: string
  chapter_id: string
  chapter_title: string
  change_type: string
  field_name: string
  old_value: string | null
  new_value: string | null
  confirmed: boolean
  created_at: string
}

interface AssistantToolLog {
  tool: string
  status: string
  detail?: string
}

interface AIRunLog {
  key: string
  tool?: string
  status?: string
  message: string
}

interface AssistantRoleplayResult {
  character_id: string
  character_name: string
  should_act: boolean
  action_type: string
  content: string
  rationale?: string
}

interface AssistantResponse {
  reply: string
  reasonableness: string
  issues: string[]
  suggestions: string[]
  worldbuilding_suggestions: Array<{ dimension: string; title: string; content: string; reason?: string }>
  chapter_draft?: {
    should_create?: boolean
    title?: string
    content?: string
    summary?: string
    involved_characters?: string[]
  }
  created_chapter?: { id: string; title: string; outline_node_id?: string | null; word_count: number } | null
  plan?: { intent?: string; tools?: string[]; reason?: string }
  tool_logs: AssistantToolLog[]
  roleplay_results: AssistantRoleplayResult[]
  message?: AssistantPersistedMessage
  conversation?: AssistantConversation
}

interface AssistantMessage {
  id?: string
  conversation_id?: string
  role: 'user' | 'assistant'
  content: string
  status?: string
  created_at?: string
  updated_at?: string
  data?: AssistantResponse
}

interface AssistantConversation {
  id: string
  project_id: string
  title: string
  current_chapter_id?: string | null
  current_outline_node_id?: string | null
  model?: string | null
  message_count?: number
  created_at?: string | null
  updated_at?: string | null
}

interface AssistantPersistedMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  payload?: AssistantResponse | null
  status: string
  created_at?: string | null
  updated_at?: string | null
}

const createEmptyAssistantResponse = (toolLogs: AssistantToolLog[] = []): AssistantResponse => ({
  reply: '',
  reasonableness: 'unclear',
  issues: [],
  suggestions: [],
  worldbuilding_suggestions: [],
  chapter_draft: { should_create: false, title: '', content: '', summary: '', involved_characters: [] },
  created_chapter: null,
  tool_logs: toolLogs,
  roleplay_results: [],
})

const toAssistantMessage = (message: AssistantPersistedMessage): AssistantMessage => ({
  id: message.id,
  conversation_id: message.conversation_id,
  role: message.role,
  content: message.content,
  status: message.status,
  created_at: message.created_at || undefined,
  updated_at: message.updated_at || undefined,
  data: message.role === 'assistant' && message.payload
    ? {
      ...createEmptyAssistantResponse(),
      ...message.payload,
      tool_logs: message.payload.tool_logs || [],
      roleplay_results: message.payload.roleplay_results || [],
      issues: message.payload.issues || [],
      suggestions: message.payload.suggestions || [],
      worldbuilding_suggestions: message.payload.worldbuilding_suggestions || [],
    }
    : undefined,
})

function extractStreamingContent(raw: string): string {
  for (const marker of ['"content":"', '"content": "']) {
    const idx = raw.indexOf(marker)
    if (idx < 0) continue
    let pos = idx + marker.length
    let out = ''
    while (pos < raw.length) {
      const ch = raw[pos]
      if (ch === '\\' && pos + 1 < raw.length) {
        const next = raw[pos + 1]
        if (next === 'n') { out += '\n'; pos += 2; continue }
        if (next === 'r') { out += '\r'; pos += 2; continue }
        if (next === 't') { out += '\t'; pos += 2; continue }
        if (next === '"' || next === '\\' || next === '/') { out += next; pos += 2; continue }
        if (next === 'u') { pos += 6; continue }
      }
      if (ch === '"' && /^\s*[,}]/.test(raw.slice(pos + 1, pos + 10))) break
      out += ch
      pos += 1
    }
    return out
  }
  return ''
}

interface WriterPageProps {
  projectId: string
}

const STATUS_COLOR: Record<string, string> = {
  pending: 'default',
  in_progress: 'processing',
  completed: 'success',
}

const TRIGGER_LABEL: Record<string, string> = {
  manual_save: '手动保存',
  ai_insert: 'AI 插入',
  restore: '版本恢复',
}

function flattenOutline(nodes: OutlineNode[], depth = 0, prefix: string[] = []): Array<{
  id: string
  title: string
  depth: number
  path: string[]
}> {
  return nodes.flatMap((node) => {
    const path = [...prefix, node.title]
    return [
      { id: node.id, title: node.title, depth, path },
      ...flattenOutline(node.children || [], depth + 1, path),
    ]
  })
}

function WriterPage({ projectId }: WriterPageProps) {
  const [form] = Form.useForm<ChapterFormValues>()
  const [chapters, setChapters] = useState<ChapterItem[]>([])
  const [outlineOptions, setOutlineOptions] = useState<Array<{ value: string; label: string }>>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ChapterDetail | null>(null)
  const [snapshots, setSnapshots] = useState<SnapshotItem[]>([])
  const [creating, setCreating] = useState(false)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [diffLoading, setDiffLoading] = useState(false)
  const [fromSnapshotId, setFromSnapshotId] = useState<string | undefined>()
  const [toSnapshotId, setToSnapshotId] = useState<string | undefined>()
  const [diff, setDiff] = useState<DiffResponse | null>(null)

  // AI assistant state
  const [aiMode, setAiMode] = useState<AIMode>('assistant')
  const [aiCharIds, setAiCharIds] = useState<string[]>([])
  const [aiPrompt, setAiPrompt] = useState('')
  const [aiTargetLength, setAiTargetLength] = useState(1000)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [aiOutput, setAiOutput] = useState('')
  const [aiBattleDialogue, setAiBattleDialogue] = useState<Array<{ character_id: string; character_name: string; content: string }>>([])
  const [aiConflicts, setAiConflicts] = useState<ConflictItem[]>([])
  const [aiRunLogs, setAiRunLogs] = useState<AIRunLog[]>([])
  const [assistantConversations, setAssistantConversations] = useState<AssistantConversation[]>([])
  const [activeAssistantConversationId, setActiveAssistantConversationId] = useState<string | null>(null)
  const [assistantHistoryLoading, setAssistantHistoryLoading] = useState(false)
  const [editingAssistantMessageId, setEditingAssistantMessageId] = useState<string | null>(null)
  const [assistantMessages, setAssistantMessages] = useState<AssistantMessage[]>([])
  const [assistantAutoCreate, setAssistantAutoCreate] = useState(true)
  const [aiPanelCollapsed, setAiPanelCollapsed] = useState(false)
  const [adoptingConflictIndex, setAdoptingConflictIndex] = useState<number | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [changeLogs, setChangeLogs] = useState<ChangeLogItem[]>([])
  const [characters, setCharacters] = useState<CharacterItem[]>([])
  const [narrativePerspective, setNarrativePerspective] = useState('third_person')
  const [writingStyle, setWritingStyle] = useState('natural')
  const [forbiddenSentencePatterns, setForbiddenSentencePatterns] = useState(DEFAULT_FORBIDDEN_SENTENCE_PATTERNS)
  const [rhetoricGuidelines, setRhetoricGuidelines] = useState(DEFAULT_RHETORIC_GUIDELINES)
  const [styleSaving, setStyleSaving] = useState(false)
  const [textOpsStyle, setTextOpsStyle] = useState<string>('')
  const [aiModel, setAiModel] = useState<string | undefined>()
  const { modelOptions, defaultModel, loading: modelsLoading } = useModelOptions()
  const aiAbortRef = useRef<AbortController | null>(null)
  const aiOutputRef = useRef<HTMLDivElement>(null)
  const assistantInputRef = useRef<HTMLTextAreaElement | null>(null)
  const editorSelectionRef = useRef<{ start: number; end: number } | null>(null)

  const fetchChapters = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<{ items: ChapterItem[]; total: number }>>(`/projects/${projectId}/chapters`)
      setChapters(res.data.data.items)
      if (!selectedId && !creating && res.data.data.items.length > 0) {
        setSelectedId(res.data.data.items[0].id)
      }
      if (selectedId && !res.data.data.items.some((item) => item.id === selectedId)) {
        setSelectedId(res.data.data.items[0]?.id || null)
      }
    } catch (err: any) {
      message.error(err.message || '获取章节列表失败')
    } finally {
      setLoading(false)
    }
  }, [creating, projectId, selectedId])

  const fetchOutline = useCallback(async () => {
    try {
      const res = await apiClient.get<ApiResponse<{ items: OutlineNode[]; flat: OutlineNode[]; total: number }>>(`/projects/${projectId}/outline`)
      const flattened = flattenOutline(res.data.data.items)
      setOutlineOptions(flattened.map((item) => ({ value: item.id, label: `${'　'.repeat(item.depth)}${item.path.join(' / ')}` })))
    } catch (err: any) {
      message.error(err.message || '获取大纲失败')
    }
  }, [projectId])

  const fetchCharacters = useCallback(async () => {
    try {
      const res = await apiClient.get<ApiResponse<{ items: CharacterItem[]; total: number }>>(`/projects/${projectId}/characters`)
      setCharacters(res.data.data.items)
    } catch {
      // ignore
    }
  }, [projectId])

  const fetchProjectStyle = useCallback(async () => {
    try {
      const res = await apiClient.get<ApiResponse<{
        narrative_perspective: string
        writing_style: string
        forbidden_sentence_patterns?: string | null
        rhetoric_guidelines?: string | null
      }>>(`/projects/${projectId}`)
      if (res.data.data.narrative_perspective) setNarrativePerspective(res.data.data.narrative_perspective)
      if (res.data.data.writing_style) setWritingStyle(res.data.data.writing_style)
      setForbiddenSentencePatterns(res.data.data.forbidden_sentence_patterns || DEFAULT_FORBIDDEN_SENTENCE_PATTERNS)
      setRhetoricGuidelines(res.data.data.rhetoric_guidelines || DEFAULT_RHETORIC_GUIDELINES)
    } catch {
      // use defaults
    }
  }, [projectId])

  const fetchAssistantConversations = useCallback(async () => {
    try {
      const res = await apiClient.get<ApiResponse<{ items: AssistantConversation[]; total: number }>>(
        `/projects/${projectId}/ai/assistant/conversations`,
      )
      const items = res.data.data.items || []
      setAssistantConversations(items)
      return items
    } catch {
      return []
    }
  }, [projectId])

  const loadAssistantConversation = useCallback(async (conversationId: string) => {
    setAssistantHistoryLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<{ conversation: AssistantConversation; messages: AssistantPersistedMessage[] }>>(
        `/projects/${projectId}/ai/assistant/conversations/${conversationId}`,
      )
      setActiveAssistantConversationId(res.data.data.conversation.id)
      setAssistantMessages((res.data.data.messages || []).map(toAssistantMessage))
      setAssistantConversations((prev) => {
        const exists = prev.some((item) => item.id === res.data.data.conversation.id)
        return exists
          ? prev.map((item) => item.id === res.data.data.conversation.id ? res.data.data.conversation : item)
          : [res.data.data.conversation, ...prev]
      })
      setEditingAssistantMessageId(null)
      setAiPrompt('')
      resetAiRunLogs()
    } catch (err: any) {
      message.error(err.message || '加载助手对话失败')
    } finally {
      setAssistantHistoryLoading(false)
    }
  }, [projectId])

  const refreshAssistantConversations = useCallback(async () => {
    const items = await fetchAssistantConversations()
    setAssistantConversations(items)
    return items
  }, [fetchAssistantConversations])

  const saveStyle = async (
    perspective: string,
    style: string,
    forbiddenPatterns = forbiddenSentencePatterns,
    rhetoricRules = rhetoricGuidelines,
  ) => {
    setStyleSaving(true)
    try {
      await apiClient.put(`/projects/${projectId}`, {
        narrative_perspective: perspective,
        writing_style: style,
        forbidden_sentence_patterns: forbiddenPatterns,
        rhetoric_guidelines: rhetoricRules,
      })
    } catch (err: any) {
      message.error(err.message || '风格设置保存失败')
    } finally {
      setStyleSaving(false)
    }
  }

  const fetchSnapshots = useCallback(async (chapterId: string) => {
    try {
      const res = await apiClient.get<ApiResponse<{ items: SnapshotItem[]; total: number }>>(`/projects/${projectId}/chapters/${chapterId}/snapshots`)
      const items = res.data.data.items
      setSnapshots(items)
      setDiff(null)
      setFromSnapshotId(items[1]?.id || items[0]?.id)
      setToSnapshotId(items[0]?.id)
    } catch {
      // ignore
    }
  }, [projectId])

  const fetchDetail = useCallback(async (chapterId: string) => {
    try {
      const res = await apiClient.get<ApiResponse<ChapterDetail>>(`/projects/${projectId}/chapters/${chapterId}`)
      setDetail(res.data.data)
      setCreating(false)
      form.setFieldsValue({
        title: res.data.data.title,
        outline_node_id: res.data.data.outline_node_id || undefined,
        content: res.data.data.content,
      })
      fetchSnapshots(chapterId)
    } catch (err: any) {
      message.error(err.message || '获取章节详情失败')
    }
  }, [fetchSnapshots, form, projectId])

  useEffect(() => {
    fetchOutline()
    fetchCharacters()
    fetchChapters()
    fetchProjectStyle()
    fetchAssistantConversations().then((items) => {
      if (items[0]) loadAssistantConversation(items[0].id)
    })
  }, [fetchAssistantConversations, fetchChapters, fetchCharacters, fetchOutline, fetchProjectStyle, loadAssistantConversation])

  useEffect(() => {
    if (!aiModel && defaultModel) {
      setAiModel(defaultModel)
    }
  }, [aiModel, defaultModel])

  useEffect(() => {
    if (selectedId) {
      fetchDetail(selectedId)
      fetchChangeLogs()
    } else if (!creating) {
      setDetail(null)
      setSnapshots([])
      setChangeLogs([])
      form.resetFields()
    }
  }, [creating, fetchDetail, form, selectedId])

  const startCreate = () => {
    setCreating(true)
    setSelectedId(null)
    setDetail(null)
    setSnapshots([])
    setDiff(null)
    form.setFieldsValue({ title: '', outline_node_id: undefined, content: '' })
  }

  const saveChapter = async (values: ChapterFormValues) => {
    if (!values.title.trim()) { message.warning('请输入章节标题'); return }
    setSaving(true)
    try {
      const payload = { title: values.title.trim(), outline_node_id: values.outline_node_id || null, content: values.content || '' }
      if (creating || !selectedId) {
        const res = await apiClient.post<ApiResponse<ChapterDetail>>(`/projects/${projectId}/chapters`, payload)
        setSelectedId(res.data.data.id)
        setCreating(false)
        message.success('章节已创建')
      } else {
        const res = await apiClient.put<ApiResponse<ChapterDetail>>(`/projects/${projectId}/chapters/${selectedId}`, { ...payload, trigger_type: 'manual_save' })
        setDetail(res.data.data)
        message.success('章节已保存并创建快照')
        fetchSnapshots(selectedId)
      }
      fetchChapters()
    } catch (err: any) {
      message.error(err.message || '保存章节失败')
    } finally {
      setSaving(false)
    }
  }

  const deleteChapter = async () => {
    if (!selectedId) return
    try {
      await apiClient.delete(`/projects/${projectId}/chapters/${selectedId}`)
      message.success('章节已删除')
      setSelectedId(null)
      setDetail(null)
      fetchChapters()
    } catch (err: any) {
      message.error(err.message || '删除章节失败')
    }
  }

  const restoreSnapshot = async (snapshotId: string) => {
    if (!selectedId) return
    try {
      const res = await apiClient.post<ApiResponse<ChapterDetail>>(`/projects/${projectId}/chapters/${selectedId}/restore/${snapshotId}`)
      setDetail(res.data.data)
      form.setFieldsValue({ title: res.data.data.title, outline_node_id: res.data.data.outline_node_id || undefined, content: res.data.data.content })
      message.success('已恢复历史版本')
      fetchSnapshots(selectedId)
      fetchChapters()
    } catch (err: any) {
      message.error(err.message || '恢复版本失败')
    }
  }

  const compareSnapshots = async () => {
    if (!selectedId || !fromSnapshotId || !toSnapshotId) return
    if (fromSnapshotId === toSnapshotId) { message.warning('请选择两个不同版本'); return }
    setDiffLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<DiffResponse>>(`/projects/${projectId}/chapters/${selectedId}/snapshots/diff`, { from_snapshot_id: fromSnapshotId, to_snapshot_id: toSnapshotId })
      setDiff(res.data.data)
    } catch (err: any) {
      message.error(err.message || '版本对比失败')
    } finally {
      setDiffLoading(false)
    }
  }

  const resetAiRunLogs = (messageText?: string, tool?: string) => {
    setAiRunLogs(messageText ? [{
      key: `${Date.now()}-start`,
      tool,
      status: 'running',
      message: messageText,
    }] : [])
  }

  const addAiRunLog = (log: Omit<AIRunLog, 'key'>) => {
    setAiRunLogs((prev) => [
      ...prev.slice(-19),
      { ...log, key: `${Date.now()}-${Math.random().toString(36).slice(2)}` },
    ])
  }

  const updateLatestAssistant = (updater: (message: AssistantMessage) => AssistantMessage) => {
    setAssistantMessages((prev) => {
      const next = [...prev]
      const index = [...next].reverse().findIndex((item) => item.role === 'assistant')
      if (index < 0) return prev
      const realIndex = next.length - 1 - index
      next[realIndex] = updater(next[realIndex])
      return next
    })
  }

  const appendAssistantToolLog = (log: AssistantToolLog, content?: string) => {
    updateLatestAssistant((item) => {
      const data = item.data || createEmptyAssistantResponse()
      return {
        ...item,
        content: content || item.content,
        data: {
          ...data,
          tool_logs: [...(data.tool_logs || []), log],
        },
      }
    })
  }

  const upsertAssistantConversation = (conversation?: AssistantConversation | null) => {
    if (!conversation) return
    setAssistantConversations((prev) => {
      const next = prev.some((item) => item.id === conversation.id)
        ? prev.map((item) => item.id === conversation.id ? conversation : item)
        : [conversation, ...prev]
      return next.sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
    })
  }

  const startNewAssistantConversation = () => {
    if (aiGenerating) {
      handleStopGeneration()
    }
    setActiveAssistantConversationId(null)
    setAssistantMessages([])
    setEditingAssistantMessageId(null)
    setAiPrompt('')
    setAiOutput('')
    resetAiRunLogs()
  }

  const deleteAssistantConversation = async (conversationId: string) => {
    try {
      await apiClient.delete(`/projects/${projectId}/ai/assistant/conversations/${conversationId}`)
      setAssistantConversations((prev) => prev.filter((item) => item.id !== conversationId))
      if (activeAssistantConversationId === conversationId) {
        setActiveAssistantConversationId(null)
        setAssistantMessages([])
        setEditingAssistantMessageId(null)
        setAiPrompt('')
      }
      message.success('对话已删除')
    } catch (err: any) {
      message.error(err.message || '删除对话失败')
    }
  }

  const editAssistantUserMessage = (item: AssistantMessage) => {
    if (!item.id) return
    setEditingAssistantMessageId(item.id)
    setAiPrompt(item.content)
    window.setTimeout(() => assistantInputRef.current?.focus(), 0)
  }

  const cancelAssistantEdit = () => {
    setEditingAssistantMessageId(null)
    setAiPrompt('')
  }

  // ── AI Generation ──────────────────────────────────────────────
  const handleAssistantChat = async () => {
    const userMessage = aiPrompt.trim()
    if (!userMessage) { message.warning('请输入要和AI助手讨论的需求'); return }

    const editMessageId = editingAssistantMessageId
    setAiGenerating(true)
    setAiOutput('')
    setAiBattleDialogue([])
    setAiConflicts([])
    resetAiRunLogs('正在提交给自动助手', 'assistant')
    const controller = new AbortController()
    aiAbortRef.current = controller
    if (editMessageId) {
      setAssistantMessages((prev) => {
        const index = prev.findIndex((item) => item.id === editMessageId)
        if (index < 0) return prev
        return [
          ...prev.slice(0, index),
          { ...prev[index], content: userMessage, status: 'completed' },
          {
            role: 'assistant',
            content: '正在规划需要调用哪些资料和角色AI...',
            status: 'running',
            data: createEmptyAssistantResponse([{ tool: 'assistant', status: 'running', detail: '正在规划工具' }]),
          },
        ]
      })
    } else {
      setAssistantMessages((prev) => [
        ...prev,
        { role: 'user', content: userMessage, status: 'completed' },
        {
          role: 'assistant',
          content: '正在规划需要调用哪些资料和角色AI...',
          status: 'running',
          data: createEmptyAssistantResponse([{ tool: 'assistant', status: 'running', detail: '正在规划工具' }]),
        },
      ])
    }
    setEditingAssistantMessageId(null)
    setAiPrompt('')

    try {
      const history = assistantMessages.slice(-6).map((item) => ({
        role: item.role,
        content: item.role === 'assistant' && item.data?.chapter_draft?.content
          ? `${item.content}\n\n【上一轮章节草稿】\n标题：${item.data.chapter_draft.title || '未命名章节'}\n${item.data.chapter_draft.content}`
          : item.content,
      }))
      const res = await fetch(`/api/v1/projects/${projectId}/ai/assistant/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          target_length: aiTargetLength,
          conversation_id: activeAssistantConversationId || undefined,
          edit_message_id: editMessageId || undefined,
          chapter_id: selectedId || undefined,
          outline_node_id: form.getFieldValue('outline_node_id') || undefined,
          model: aiModel || defaultModel || undefined,
          max_tokens: Math.ceil(aiTargetLength * 2.2),
          auto_create_chapter: assistantAutoCreate,
          history,
        }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) throw new Error('请求失败')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let completed = false
      let finalTokenStarted = false
      let rawStream = ''
      let lastContentSync = 0

      const handleFrame = (frame: string) => {
        const data = frame
          .split(/\r?\n/)
          .filter((line) => line.startsWith('data:'))
          .map((line) => line.replace(/^data:\s?/, ''))
          .join('\n')
        if (!data || data === '[DONE]') return
        const event = JSON.parse(data)
        if (event.type === 'conversation') {
          const conversation = event.conversation as AssistantConversation
          const persistedUser = event.user_message as AssistantPersistedMessage
          const persistedAssistant = event.assistant_message as AssistantPersistedMessage
          setActiveAssistantConversationId(conversation.id)
          upsertAssistantConversation(conversation)
          setAssistantMessages((prev) => {
            if (editMessageId) {
              const index = prev.findIndex((item) => item.id === editMessageId)
              if (index >= 0) {
                return [
                  ...prev.slice(0, index),
                  toAssistantMessage(persistedUser),
                  toAssistantMessage(persistedAssistant),
                ]
              }
            }
            const next = [...prev]
            const assistantIndex = [...next].reverse().findIndex((item) => item.role === 'assistant')
            const realAssistantIndex = assistantIndex >= 0 ? next.length - 1 - assistantIndex : -1
            if (realAssistantIndex >= 1 && !next[realAssistantIndex].id && !next[realAssistantIndex - 1].id) {
              next.splice(realAssistantIndex - 1, 2, toAssistantMessage(persistedUser), toAssistantMessage(persistedAssistant))
              return next
            }
            return [...prev, toAssistantMessage(persistedUser), toAssistantMessage(persistedAssistant)]
          })
        } else if (event.type === 'status') {
          const detail = event.message || '正在执行'
          const log = { tool: event.tool || 'assistant', status: 'running', detail }
          addAiRunLog({ tool: log.tool, status: log.status, message: detail })
          appendAssistantToolLog(log, `正在执行：${detail}`)
        } else if (event.type === 'tool') {
          const detail = event.detail || event.message || event.tool
          const log = { tool: event.tool || 'tool', status: event.status || 'ok', detail }
          addAiRunLog({ tool: log.tool, status: log.status, message: `${log.tool}: ${detail}` })
          appendAssistantToolLog(log)
        } else if (event.type === 'draft_chapter') {
          const chapter = event.chapter as { id: string; title: string; outline_node_id?: string | null } | undefined
            if (chapter?.id) {
              addAiRunLog({ tool: 'create_chapter', status: 'running', message: `已创建章节占位：${chapter.title}` })
              fetchChapters()
              setSelectedId(chapter.id)
              form.setFieldsValue({ title: chapter.title, outline_node_id: chapter.outline_node_id || undefined, content: '' })
            }
        } else if (event.type === 'token') {
          if (!finalTokenStarted) {
            finalTokenStarted = true
            addAiRunLog({ tool: 'final_writer', status: 'running', message: '总控AI开始输出最终回复' })
            updateLatestAssistant((item) => ({ ...item, content: '总控AI正在生成最终回复...' }))
          }
          const token = (event as { type: 'token'; content?: string }).content || ''
          if (token) {
            setAiOutput((prev) => prev + token)
            rawStream += token
            const now = Date.now()
            if (now - lastContentSync > 120) {
              lastContentSync = now
              const content = extractStreamingContent(rawStream)
              if (content) form.setFieldsValue({ content })
            }
          }
        } else if (event.type === 'complete') {
          const payload = event.data as AssistantResponse
          completed = true
          upsertAssistantConversation(payload.conversation)
          setAssistantMessages((prev) => {
            const next = [...prev]
            const index = [...next].reverse().findIndex((item) => item.role === 'assistant')
            if (index < 0) return [...prev, { role: 'assistant', content: payload.reply || '已完成分析。', data: payload }]
            const realIndex = next.length - 1 - index
            next[realIndex] = {
              id: payload.message?.id || next[realIndex].id,
              conversation_id: payload.message?.conversation_id || next[realIndex].conversation_id,
              role: 'assistant',
              content: payload.reply || '已完成分析。',
              status: payload.message?.status || 'completed',
              created_at: payload.message?.created_at || next[realIndex].created_at,
              updated_at: payload.message?.updated_at || next[realIndex].updated_at,
              data: payload,
            }
            return next
          })
          const draftText = payload.chapter_draft?.content?.trim()
          setAiOutput(draftText || '')
          addAiRunLog({ tool: 'assistant', status: 'ok', message: '自动助手已完成' })
          if (payload.created_chapter?.id) {
            message.success(`已创建章节：${payload.created_chapter.title}`)
            fetchChapters()
            setSelectedId(payload.created_chapter.id)
            // Set form content immediately from parsed JSON — no API wait needed
            const content = payload.chapter_draft?.content || ''
            form.setFieldsValue({
              title: payload.created_chapter.title,
              content,
              outline_node_id: payload.created_chapter.outline_node_id || undefined,
            })
            // Sync with DB in background for metadata accuracy
            fetchDetail(payload.created_chapter.id)
          }
          refreshAssistantConversations()
        } else if (event.type === 'error') {
          throw new Error(event.message || 'AI助手执行失败')
        }
      }

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const frames = buffer.split(/\r?\n\r?\n/)
        buffer = frames.pop() || ''
        for (const frame of frames) {
          if (frame.trim()) handleFrame(frame)
        }
      }
      buffer += decoder.decode()
      if (buffer.trim()) handleFrame(buffer)
      if (!completed && !controller.signal.aborted) {
        throw new Error('AI助手没有返回完整结果')
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        message.error(err.message || 'AI助手执行失败')
        addAiRunLog({ tool: 'assistant', status: 'error', message: err.message || 'AI助手执行失败' })
        updateLatestAssistant((item) => ({ ...item, content: err.message || 'AI助手执行失败', status: 'error' }))
      }
    } finally {
      setAiGenerating(false)
      aiAbortRef.current = null
    }
  }

  const handleGenerate = async () => {
    if (aiMode === 'assistant') { handleAssistantChat(); return }
    if (aiMode === 'conflict') { handleConflictGenerate(); return }
    if (!aiPrompt.trim()) { message.warning('请输入AI指令'); return }
    if (aiMode === 'character' && aiCharIds.length === 0) { message.warning('请选择角色'); return }
    if (aiMode === 'battle' && aiCharIds.length < 2) { message.warning('对戏模式需要至少2个角色'); return }

    setAiGenerating(true)
    setAiOutput('')
    setAiBattleDialogue([])
    setAiConflicts([])
    resetAiRunLogs(
      aiMode === 'battle'
        ? '正在准备多角色对戏上下文'
        : aiMode === 'character'
          ? '正在准备角色档案和上下文'
          : '正在准备叙述者上下文',
      aiMode,
    )
    const controller = new AbortController()
    aiAbortRef.current = controller

    const currentOutlineNodeId = form.getFieldValue('outline_node_id') || undefined
    const promptWithLength = `${aiPrompt}\n\n长度目标：约 ${aiTargetLength} 字。`
    const maxTokens = Math.ceil(aiTargetLength * 1.8)
    const selectedModel = aiModel || defaultModel

    let url = ''
    let body: Record<string, unknown> = {}
    if (aiMode === 'narrator') {
      url = `/projects/${projectId}/ai/generate/narrator`
      body = { prompt: promptWithLength, chapter_id: selectedId || undefined, outline_node_id: currentOutlineNodeId, max_tokens: maxTokens, model: selectedModel || undefined }
    } else if (aiMode === 'character') {
      url = `/projects/${projectId}/ai/generate/character/${aiCharIds[0]}`
      body = { prompt: promptWithLength, chapter_id: selectedId || undefined, outline_node_id: currentOutlineNodeId, max_tokens: maxTokens, model: selectedModel || undefined }
    } else {
      url = `/projects/${projectId}/ai/generate/dialogue-battle`
      body = { prompt: promptWithLength, character_ids: aiCharIds, turns: 3, chapter_id: selectedId || undefined, outline_node_id: currentOutlineNodeId, max_tokens: maxTokens, model: selectedModel || undefined }
    }

    try {
      addAiRunLog({ tool: aiMode, status: 'running', message: `正在调用模型：${selectedModel || '默认模型'}` })
      const res = await fetch(`/api/v1${url}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) throw new Error('请求失败')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let tokenStarted = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const raw = line.slice(6)
          if (raw === '[DONE]') break
          try {
            const event = JSON.parse(raw)
            if (event.type === 'token') {
              if (!tokenStarted) {
                tokenStarted = true
                addAiRunLog({ tool: aiMode, status: 'running', message: '模型开始实时输出正文' })
              }
              setAiOutput((prev) => prev + event.content)
            } else if (event.type === 'turn_start') {
              addAiRunLog({ tool: 'roleplay_characters', status: 'running', message: `正在调用角色AI：${event.character_name}` })
              setAiBattleDialogue((prev) => [...prev, { character_id: event.character_id, character_name: event.character_name, content: '' }])
            } else if (event.type === 'turn_end') {
              addAiRunLog({ tool: 'roleplay_characters', status: 'ok', message: `${event.character_name} 已完成本轮发言` })
              setAiBattleDialogue((prev) => prev.map((d, i) => i === prev.length - 1 ? { ...d, content: event.full_text } : d))
            } else if (event.type === 'battle_complete') {
              addAiRunLog({ tool: 'dialogue_battle', status: 'ok', message: '多角色对戏已完成' })
            } else if (event.type === 'style_check') {
              addAiRunLog({ tool: 'style_guard', status: 'running', message: event.message || '正在检查禁用句式' })
            } else if (event.type === 'style_repaired') {
              if (event.full_text) setAiOutput(event.full_text)
              addAiRunLog({
                tool: 'style_guard',
                status: event.status || 'ok',
                message: event.message || '禁用句式检查完成',
              })
            } else if (event.type === 'done') {
              setAiOutput(event.full_text || '')
              addAiRunLog({ tool: aiMode, status: 'ok', message: '生成完成' })
            } else if (event.type === 'error') {
              addAiRunLog({ tool: aiMode, status: 'error', message: event.message })
              message.error(event.message)
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        addAiRunLog({ tool: aiMode, status: 'error', message: err.message || 'AI生成失败，请检查模型配置' })
        message.error(err.message || 'AI生成失败，请检查模型配置')
      }
    } finally {
      setAiGenerating(false)
      aiAbortRef.current = null
    }
  }

  const handleStopGeneration = () => {
    aiAbortRef.current?.abort()
    setAiGenerating(false)
    addAiRunLog({ tool: 'assistant', status: 'skipped', message: '已停止当前AI任务' })
    if (aiMode === 'assistant') {
      updateLatestAssistant((item) => ({ ...item, content: '已停止生成。', status: 'aborted' }))
      refreshAssistantConversations()
    }
  }

  const handleConflictGenerate = async () => {
    setAiGenerating(true)
    setAiConflicts([])
    resetAiRunLogs('正在读取大纲、摘要、角色与关系来设计冲突', 'conflict_suggest')
    const controller = new AbortController()
    aiAbortRef.current = controller

    try {
      addAiRunLog({ tool: 'conflict_suggest', status: 'running', message: `正在调用模型：${aiModel || defaultModel || '默认模型'}` })
      const res = await fetch(`/api/v1/projects/${projectId}/ai/conflict-suggest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_id: selectedId || undefined,
          outline_node_id: form.getFieldValue('outline_node_id') || undefined,
          prompt: aiPrompt || undefined,
          model: aiModel || defaultModel || undefined,
        }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error('请求失败')
      const data = await res.json()
      if (data.code === 0 && data.data) {
        setAiConflicts(data.data.conflicts || [])
        addAiRunLog({ tool: 'conflict_suggest', status: 'ok', message: `已生成 ${data.data.conflicts?.length || 0} 条冲突建议` })
        if (!data.data.conflicts?.length) {
          message.info('未能生成冲突建议，请再试一次')
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        addAiRunLog({ tool: 'conflict_suggest', status: 'error', message: err.message || '冲突建议生成失败' })
        message.error(err.message || '冲突建议生成失败')
      }
    } finally {
      setAiGenerating(false)
      aiAbortRef.current = null
    }
  }

  const handleAdoptConflict = async (conflict: ConflictItem, index: number) => {
    const outlineNodeId = form.getFieldValue('outline_node_id') || undefined
    if (!outlineNodeId) {
      message.warning('请先为当前章节关联一个大纲节点')
      return
    }

    setAdoptingConflictIndex(index)
    try {
      await apiClient.post<ApiResponse<{ outline_node: unknown }>>(`/projects/${projectId}/ai/conflict-adopt`, {
        outline_node_id: outlineNodeId,
        type: conflict.type,
        title: conflict.title,
        description: conflict.description,
        suggested_outcome: conflict.suggested_outcome,
        involved_characters: conflict.involved_characters || [],
      })
      message.success('已创建冲突大纲子节点')
      setAiConflicts((prev) => prev.filter((_, itemIndex) => itemIndex !== index))
      fetchOutline()
    } catch (err: any) {
      message.error(err.message || '采纳冲突建议失败')
    } finally {
      setAdoptingConflictIndex(null)
    }
  }

  const fetchChangeLogs = async () => {
    if (!selectedId) return
    try {
      const res = await apiClient.get<ApiResponse<{ items: ChangeLogItem[]; total: number }>>(
        `/projects/${projectId}/characters/change-logs`,
        { chapter_id: selectedId, confirmed: false }
      )
      setChangeLogs(res.data.data.items)
    } catch {
      // ignore
    }
  }

  const handleDetectChanges = async () => {
    if (!selectedId) { message.warning('请先选择一个章节'); return }
    setDetecting(true)
    try {
      const res = await apiClient.post<ApiResponse<{ changes: unknown[]; total: number }>>(
        `/projects/${projectId}/ai/character-changes/${selectedId}`,
        { model: aiModel || defaultModel || undefined },
      )
      const count = res.data.data.total
      if (count > 0) {
        message.success(`检测到 ${count} 处角色变化`)
        fetchChangeLogs()
      } else {
        message.info('未检测到明显的角色变化')
      }
    } catch (err: any) {
      message.error(err.message || '角色变化检测失败')
    } finally {
      setDetecting(false)
    }
  }

  const confirmChange = async (logId: string) => {
    try {
      await apiClient.put(`/projects/${projectId}/characters/change-logs/${logId}/confirm`)
      message.success('变更已确认并应用')
      setChangeLogs((prev) => prev.filter((l) => l.id !== logId))
    } catch (err: any) {
      message.error(err.message || '确认失败')
    }
  }

  const rejectChange = async (logId: string) => {
    try {
      await apiClient.delete(`/projects/${projectId}/characters/change-logs/${logId}`)
      setChangeLogs((prev) => prev.filter((l) => l.id !== logId))
    } catch (err: any) {
      message.error(err.message || '拒绝失败')
    }
  }

  const handleBatchChanges = async (action: 'confirm' | 'reject') => {
    if (!selectedId) return
    try {
      await apiClient.post(`/projects/${projectId}/characters/change-logs/batch?chapter_id=${selectedId}&action=${action}`)
      message.success(action === 'confirm' ? '已全部确认并应用' : '已全部忽略')
      setChangeLogs([])
    } catch (err: any) {
      message.error(err.message || '批量操作失败')
    }
  }

  const getSelectedText = (): string => {
    const el = document.querySelector<HTMLTextAreaElement>('.writer-content-input')
    if (!el) return ''
    const start = el.selectionStart ?? 0
    const end = el.selectionEnd ?? 0
    editorSelectionRef.current = { start, end }
    return el.value.substring(start, end)
  }

  const getContentTextArea = () => document.querySelector<HTMLTextAreaElement>('.writer-content-input')

  const captureEditorSelection = () => {
    const el = getContentTextArea()
    if (!el) return
    editorSelectionRef.current = {
      start: el.selectionStart ?? 0,
      end: el.selectionEnd ?? 0,
    }
  }

  const getEditorSelection = (fallbackLength: number) => {
    const el = getContentTextArea()
    if (el) {
      const start = el.selectionStart ?? fallbackLength
      const end = el.selectionEnd ?? start
      editorSelectionRef.current = { start, end }
      return { start, end }
    }
    const saved = editorSelectionRef.current
    if (!saved) return { start: fallbackLength, end: fallbackLength }
    return {
      start: Math.min(saved.start, fallbackLength),
      end: Math.min(saved.end, fallbackLength),
    }
  }

  const getAiResultText = () => (
    aiMode === 'battle'
      ? aiBattleDialogue.map((d) => `【${d.character_name}】\n${d.content}`).join('\n\n')
      : aiMode === 'assistant'
        ? ([...assistantMessages].reverse().find((item) => item.role === 'assistant')?.data?.chapter_draft?.content || aiOutput)
        : aiOutput
  ).trim()

  const replaceEditorRange = (start: number, end: number, text: string) => {
    const current = form.getFieldValue('content') || ''
    const next = `${current.slice(0, start)}${text}${current.slice(end)}`
    form.setFieldValue('content', next)
    window.setTimeout(() => {
      const el = getContentTextArea()
      if (!el) return
      el.focus()
      const cursor = start + text.length
      el.setSelectionRange(cursor, cursor)
    }, 0)
  }

  const handleTextOps = async (op: 'rewrite' | 'expand' | 'continue') => {
    const selectedText = getSelectedText()
    const fullText = form.getFieldValue('content') || ''
    const text = selectedText || fullText
    if (!text.trim()) { message.warning('请先选中文本或在正文中输入内容'); return }

    setAiGenerating(true)
    setAiOutput('')
    setAiBattleDialogue([])
    setAiConflicts([])
    setAiMode('narrator')
    resetAiRunLogs(
      op === 'rewrite' ? '正在准备改写文本' : op === 'expand' ? '正在准备扩写文本' : '正在准备续写上下文',
      `text_${op}`,
    )

    const endpoints: Record<string, string> = {
      rewrite: `/projects/${projectId}/ai/rewrite`,
      expand: `/projects/${projectId}/ai/expand`,
      continue: `/projects/${projectId}/ai/continue`,
    }

    try {
      addAiRunLog({ tool: `text_${op}`, status: 'running', message: `正在调用模型：${aiModel || defaultModel || '默认模型'}` })
      const body: Record<string, unknown> = {
        text,
        prompt: aiPrompt || undefined,
        chapter_id: op === 'continue' ? (selectedId || undefined) : undefined,
        outline_node_id: op === 'continue' ? (form.getFieldValue('outline_node_id') || undefined) : undefined,
        model: aiModel || defaultModel || undefined,
      }
      if (op === 'rewrite' && textOpsStyle) body.style = textOpsStyle

      const res = await fetch(`/api/v1${endpoints[op]}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!res.ok) throw new Error('请求失败')
      const data = await res.json()
      if (data.code === 0 && data.data) {
        const result = data.data.rewritten || data.data.expanded || data.data.continuation || ''
        setAiOutput(result)
        addAiRunLog({ tool: `text_${op}`, status: 'ok', message: `${op === 'rewrite' ? '改写' : op === 'expand' ? '扩写' : '续写'}完成` })
        message.success(`${op === 'rewrite' ? '改写' : op === 'expand' ? '扩写' : '续写'}完成`)
      }
    } catch (err: any) {
      addAiRunLog({ tool: `text_${op}`, status: 'error', message: err.message || '文本操作失败' })
      message.error(err.message || '文本操作失败')
    } finally {
      setAiGenerating(false)
    }
  }

  const insertAiText = () => {
    const text = getAiResultText()
    if (!text.trim()) return
    const current = form.getFieldValue('content') || ''
    const { start, end } = getEditorSelection(current.length)
    const prefix = start > 0 && current[start - 1] !== '\n' ? '\n\n' : ''
    const suffix = end < current.length && current[end] !== '\n' ? '\n\n' : ''
    replaceEditorRange(start, end, `${prefix}${text}${suffix}`)
    message.success('AI内容已插入到光标位置')
  }

  const replaceWithAiText = () => {
    const text = getAiResultText()
    if (!text.trim()) return
    const current = form.getFieldValue('content') || ''
    const { start, end } = getEditorSelection(current.length)
    if (start === end) {
      message.warning('请先在正文中选中要替换的文本')
      return
    }
    replaceEditorRange(start, end, text)
    message.success('选中文本已替换为AI内容')
  }

  const clearAiOutput = () => {
    setAiOutput('')
    setAiBattleDialogue([])
    setAiConflicts([])
    setAiPrompt('')
  }

  const snapshotOptions = useMemo(() => snapshots.map((snapshot) => ({
    value: snapshot.id,
    label: `v${snapshot.version_number} · ${TRIGGER_LABEL[snapshot.trigger_type] || snapshot.trigger_type}`,
  })), [snapshots])

  const characterOptions = useMemo(() => characters.map((c) => ({
    value: c.id,
    label: `${c.name}${c.role_type ? ` (${c.role_type})` : ''}`,
  })), [characters])

  const editorTitle = creating ? '新建章节' : detail?.title || '章节正文'

  return (
    <div className="writer-page">
      <div className={`writer-shell${aiPanelCollapsed ? ' writer-shell-ai-collapsed' : ''}`}>
        {/* ── Left: Chapter List ── */}
        <aside className="writer-chapter-panel">
          <div className="writer-panel-head">
            <Title level={4} style={{ margin: 0 }}><FileTextOutlined /> 章节</Title>
            <Space size={6}>
              <Button icon={<ReloadOutlined />} onClick={fetchChapters} loading={loading} />
              <Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>新建</Button>
            </Space>
          </div>
          <List
            loading={loading}
            dataSource={chapters}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无章节"><Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>新建章节</Button></Empty> }}
            renderItem={(chapter) => (
              <List.Item
                className={`writer-chapter-item${chapter.id === selectedId ? ' writer-chapter-item-active' : ''}`}
                onClick={() => setSelectedId(chapter.id)}
              >
                <List.Item.Meta
                  title={<Text strong ellipsis={{ tooltip: chapter.title }} style={{ maxWidth: '100%' }}>{chapter.title}</Text>}
                  description={
                    <Space direction="vertical" size={4}>
                      <Text type="secondary" ellipsis>{chapter.outline_path.length > 0 ? chapter.outline_path.join(' / ') : '未关联大纲'}</Text>
                      {chapter.summary_text && (
                        <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0, fontSize: 12 }}>
                          {chapter.summary_text}
                        </Paragraph>
                      )}
                      <Space size={6} wrap>
                        <Tag>{chapter.word_count} 字</Tag>
                        <Tag>v{chapter.current_version}</Tag>
                        {chapter.outline_status && <Tag color={STATUS_COLOR[chapter.outline_status] || 'default'}>{chapter.outline_status}</Tag>}
                      </Space>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </aside>

        {/* ── Center: Editor ── */}
        <main className="writer-editor">
          <div className="writer-editor-head">
            <div>
              <Title level={4} style={{ margin: 0 }}>{editorTitle}</Title>
              {detail && !creating && (
                <Text type="secondary">{detail.word_count} 字 · v{detail.current_version} · {new Date(detail.updated_at).toLocaleString('zh-CN')}</Text>
              )}
            </div>
            <Space>
              {aiPanelCollapsed && (
                <Button icon={<MenuUnfoldOutlined />} onClick={() => setAiPanelCollapsed(false)}>
                  AI 助手
                </Button>
              )}
              {selectedId && !creating && (
                <>
                  <Select
                    value={textOpsStyle}
                    onChange={setTextOpsStyle}
                    allowClear
                    size="small"
                    placeholder="改写风格（可选）"
                    style={{ width: 140 }}
                    options={[
                      { value: 'vivid', label: '生动' },
                      { value: 'concise', label: '简洁' },
                      { value: 'serious', label: '严肃' },
                      { value: 'humorous', label: '幽默' },
                      { value: 'poetic', label: '诗意' },
                    ]}
                  />
                  <Button size="small" onClick={() => handleTextOps('rewrite')} disabled={aiGenerating}>改写</Button>
                  <Button size="small" onClick={() => handleTextOps('expand')} disabled={aiGenerating}>扩写</Button>
                  <Button size="small" onClick={() => handleTextOps('continue')} disabled={aiGenerating}>续写</Button>
                  <Button icon={<RobotOutlined />} loading={detecting} onClick={handleDetectChanges}>检测角色变化</Button>
                  <Popconfirm title="删除章节" description="版本历史和出场记录也会一并删除。" okText="删除" cancelText="取消"
                    okButtonProps={{ danger: true, autoInsertSpace: false }} cancelButtonProps={{ autoInsertSpace: false }}
                    onConfirm={deleteChapter}>
                    <Button danger icon={<DeleteOutlined />}>删除</Button>
                  </Popconfirm>
                </>
              )}
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => form.submit()}>保存</Button>
            </Space>
          </div>

          {!creating && !detail && chapters.length === 0 ? (
            <Alert type="info" showIcon message="先创建一个章节，正文和版本历史会从这里开始。" />
          ) : (
            <Form form={form} layout="vertical" onFinish={saveChapter}>
              <div className="writer-form-grid">
                <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入章节标题' }]}>
                  <Input placeholder="例如：第一章 风祭前夜" maxLength={200} />
                </Form.Item>
                <Form.Item name="outline_node_id" label="关联大纲">
                  <Select allowClear showSearch optionFilterProp="label" options={outlineOptions} placeholder="选择大纲节点" />
                </Form.Item>
              </div>
              {detail?.summary_text && !creating && (
                <Alert
                  type="info"
                  showIcon
                  message="章节摘要"
                  description={
                    <div>
                      <Paragraph style={{ marginBottom: detail.key_events?.length ? 8 : 0, whiteSpace: 'pre-wrap' }}>
                        {detail.summary_text}
                      </Paragraph>
                      {(detail.key_events || []).length > 0 && (
                        <Space wrap>
                          {(detail.key_events || []).slice(0, 8).map((event, index) => (
                            <Tag key={`${event}-${index}`}>{event}</Tag>
                          ))}
                        </Space>
                      )}
                    </div>
                  }
                  style={{ marginBottom: 12 }}
                />
              )}
              <Form.Item name="content" label="正文">
                <TextArea
                  className="writer-content-input"
                  placeholder="开始写这一章"
                  autoSize={{ minRows: 18, maxRows: 28 }}
                  showCount
                  onSelect={captureEditorSelection}
                  onClick={captureEditorSelection}
                  onKeyUp={captureEditorSelection}
                />
              </Form.Item>
            </Form>
          )}

          {/* ── Version History ── */}
          <section className="writer-history-section">
            <div className="writer-history-head">
              <Title level={5} style={{ margin: 0 }}><HistoryOutlined /> 版本历史</Title>
              <Space wrap>
                <Select value={fromSnapshotId} options={snapshotOptions} onChange={setFromSnapshotId} placeholder="起始版本" style={{ width: 180 }} />
                <Select value={toSnapshotId} options={snapshotOptions} onChange={setToSnapshotId} placeholder="目标版本" style={{ width: 180 }} />
                <Button icon={<DiffOutlined />} loading={diffLoading} disabled={snapshots.length < 2} onClick={compareSnapshots}>对比</Button>
              </Space>
            </div>
            {snapshots.length === 0 ? (
              <Text type="secondary">保存一次正文后，这里会出现版本快照。</Text>
            ) : (
              <Timeline className="writer-snapshot-timeline" items={snapshots.map((snapshot) => ({
                children: (
                  <div className="writer-snapshot-row">
                    <div><Text strong>v{snapshot.version_number}</Text>
                      <Text type="secondary"> · {TRIGGER_LABEL[snapshot.trigger_type] || snapshot.trigger_type} · {snapshot.word_count} 字 · {new Date(snapshot.created_at).toLocaleString('zh-CN')}</Text></div>
                    <Popconfirm title="恢复此版本" description="当前正文会被替换，并生成一条新的恢复快照。" okText="恢复" cancelText="取消" onConfirm={() => restoreSnapshot(snapshot.id)}>
                      <Button size="small" icon={<RollbackOutlined />}>恢复</Button>
                    </Popconfirm>
                  </div>
                ),
              }))} />
            )}
            {diff && (
              <div className="writer-diff-panel">
                <div className="writer-diff-summary">
                  <Text strong>v{diff.from_snapshot.version_number} → v{diff.to_snapshot.version_number}</Text>
                  <Tag color={diff.total_changes > 0 ? 'orange' : 'green'}>{diff.total_changes} 处变更</Tag>
                </div>
                {diff.changes.filter((change) => change.type !== 'equal').map((change, index) => (
                  <div className="writer-diff-change" key={`${change.type}-${index}`}>
                    <Tag color={change.type === 'insert' ? 'green' : change.type === 'delete' ? 'red' : 'orange'}>{change.type}</Tag>
                    <div className="writer-diff-columns">
                      <pre className="writer-diff-block writer-diff-old">{change.from_lines.length > 0 ? change.from_lines.join('\n') : ' '}</pre>
                      <pre className="writer-diff-block writer-diff-new">{change.to_lines.length > 0 ? change.to_lines.join('\n') : ' '}</pre>
                    </div>
                  </div>
                ))}
                {diff.total_changes === 0 && <Paragraph>两个版本没有正文差异。</Paragraph>}
              </div>
            )}

            {/* Character Change Review */}
            {changeLogs.length > 0 && (
              <div className="writer-diff-panel" style={{ borderColor: '#1677ff' }}>
                <div className="writer-diff-summary">
                  <Text strong style={{ color: '#1677ff' }}>角色变化审查</Text>
                  <Space size={4}>
                    <Tag color="blue">{changeLogs.length} 处待确认</Tag>
                    <Button size="small" type="primary" onClick={() => handleBatchChanges('confirm')}>全部确认</Button>
                    <Button size="small" danger onClick={() => handleBatchChanges('reject')}>全部忽略</Button>
                  </Space>
                </div>
                {changeLogs.map((log) => {
                  const typeLabel: Record<string, string> = { skill: '技能', experience: '经历', relationship: '关系', personality: '性格' }
                  const fieldLabel: Record<string, string> = { abilities: '能力', personality: '性格', background: '背景', appearance: '外貌' }
                  return (
                    <div className="writer-diff-change" key={log.id}>
                      <Space size={4} wrap style={{ marginBottom: 6 }}>
                        <Tag color="blue">{log.character_name}</Tag>
                        <Tag>{typeLabel[log.change_type] || log.change_type}</Tag>
                        <Tag color="purple">{fieldLabel[log.field_name] || log.field_name}</Tag>
                      </Space>
                      <div className="writer-diff-columns">
                        <div className="writer-diff-block writer-diff-old">
                          <Text type="secondary" style={{ fontSize: 11 }}>旧值</Text>
                          <Paragraph style={{ marginBottom: 0 }}>{log.old_value || '（无）'}</Paragraph>
                        </div>
                        <div className="writer-diff-block writer-diff-new">
                          <Text type="secondary" style={{ fontSize: 11 }}>新值</Text>
                          <Paragraph style={{ marginBottom: 0 }}>{log.new_value || '（无）'}</Paragraph>
                        </div>
                      </div>
                      <Space style={{ marginTop: 8 }}>
                        <Button type="primary" size="small" onClick={() => confirmChange(log.id)}>确认应用</Button>
                        <Button size="small" danger onClick={() => rejectChange(log.id)}>忽略</Button>
                      </Space>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </main>

        {/* ── Right: AI Assistant ── */}
        {!aiPanelCollapsed && (
        <aside className="writer-ai-panel">
          <div className="writer-ai-head">
            <Title level={5} style={{ margin: 0 }}><RobotOutlined /> 项目助手</Title>
            <Button
              type="text"
              size="small"
              icon={<MenuFoldOutlined />}
              onClick={() => setAiPanelCollapsed(true)}
            />
          </div>

          <WorkspaceAssistantChat
            projectId={projectId}
            scope="project"
            selectedOutlineNodeId={form.getFieldValue('outline_node_id') || undefined}
            model={aiModel}
            defaultModel={defaultModel}
            modelOptions={modelOptions}
            modelsLoading={modelsLoading}
            onModelChange={setAiModel}
            onApplied={() => {
              fetchChapters()
              fetchOutline()
              fetchCharacters()
              if (selectedId) {
                fetchDetail(selectedId)
              }
            }}
          />

          {false && (
          <div className="writer-ai-legacy">
          <Tabs activeKey={aiMode} onChange={(k) => { setAiMode(k as AIMode); clearAiOutput() }} size="small"
            items={[
              { key: 'assistant', label: <span><RobotOutlined /> 自动</span> },
              { key: 'narrator', label: <span><EditOutlined /> 叙述</span> },
              { key: 'character', label: <span><UserOutlined /> 角色</span> },
              { key: 'battle', label: <span><TeamOutlined /> 对戏</span> },
              { key: 'conflict', label: <span><DiffOutlined spin={aiGenerating && aiMode === 'conflict'} /> 冲突</span> },
            ]}
          />

          <Select
            allowClear
            showSearch
            value={aiModel}
            onChange={setAiModel}
            options={modelOptions}
            loading={modelsLoading}
            optionFilterProp="label"
            placeholder={modelOptions.length ? '选择AI模型' : '请先在系统设置配置模型'}
            notFoundContent={modelsLoading ? '加载模型中...' : '暂无已配置模型'}
            style={{ width: '100%', marginBottom: 8 }}
          />

          {(aiMode === 'character' || aiMode === 'battle') && (
            <Select
              mode={aiMode === 'battle' ? 'multiple' : undefined}
              value={aiMode === 'character' ? (aiCharIds[0] || undefined) : aiCharIds}
              onChange={(v) => setAiCharIds(Array.isArray(v) ? v : v ? [v] : [])}
              options={characterOptions}
              placeholder={aiMode === 'character' ? '选择角色' : '选择对戏角色（至少2个）'}
              style={{ width: '100%', marginBottom: 8 }}
              showSearch
              optionFilterProp="label"
            />
          )}

          {aiMode !== 'assistant' && (
            <TextArea
              value={aiPrompt}
              onChange={(e) => setAiPrompt(e.target.value)}
              placeholder={
                aiMode === 'narrator'
                  ? '描写主角进入山洞的场景...'
                  : aiMode === 'character'
                    ? '让角色对当前场景做出反应...'
                    : aiMode === 'battle'
                      ? '描述场景，角色A和角色B相遇...'
                      : '（可选）对冲突类型的要求，如"需要势力冲突"...'
              }
              autoSize={{ minRows: 3, maxRows: 5 }}
              style={{ marginBottom: 8 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerate()
              }}
            />
          )}

          {aiMode !== 'conflict' && (
            <div style={{ marginBottom: 12 }}>
              <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 2 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>生成长度</Text>
                <Text type="secondary" style={{ fontSize: 12 }}>{aiTargetLength} 字</Text>
              </Space>
              <Slider
                min={500}
                max={3000}
                step={100}
                value={aiTargetLength}
                onChange={setAiTargetLength}
                tooltip={{ formatter: (value) => `${value} 字` }}
              />
            </div>
          )}

          {aiMode === 'assistant' && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>自动创建并写入章节</Text>
              <Switch size="small" checked={assistantAutoCreate} onChange={setAssistantAutoCreate} />
            </div>
          )}

          {aiMode !== 'assistant' && (
            <Space style={{ marginBottom: 12 }}>
              {aiGenerating ? (
                <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>停止生成</Button>
              ) : (
                <Button type="primary" icon={<SendOutlined />} onClick={handleGenerate} loading={aiGenerating}>
                  {`生成 (${aiMode === 'narrator' ? '叙述者' : aiMode === 'character' ? '角色对话' : aiMode === 'battle' ? '对戏' : '冲突分析'})`}
                </Button>
              )}
            </Space>
          )}

          {aiMode === 'assistant' && (
            <div className="writer-assistant-history-panel">
              <div className="writer-assistant-history-head">
                <Text strong>历史对话</Text>
                <Space size={4}>
                  <Button size="small" icon={<ReloadOutlined />} loading={assistantHistoryLoading} onClick={refreshAssistantConversations} />
                  <Button size="small" type="primary" icon={<PlusOutlined />} onClick={startNewAssistantConversation}>
                    新对话
                  </Button>
                </Space>
              </div>
              {assistantConversations.length > 0 ? (
                <div className="writer-assistant-history-list">
                  {assistantConversations.map((conversation) => (
                    <div
                      key={conversation.id}
                      className={`writer-assistant-history-item${conversation.id === activeAssistantConversationId ? ' writer-assistant-history-item-active' : ''}`}
                      onClick={() => loadAssistantConversation(conversation.id)}
                    >
                      <Text className="writer-assistant-history-title" title={conversation.title}>
                        {conversation.title}
                      </Text>
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(event) => {
                          event.stopPropagation()
                          deleteAssistantConversation(conversation.id)
                        }}
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>还没有历史对话。</Text>
              )}
            </div>
          )}

          {aiRunLogs.length > 0 && (
            <div className="writer-ai-run-log">
              <Text type="secondary" style={{ fontSize: 12 }}>运行过程</Text>
              {aiRunLogs.map((log) => (
                <div className="writer-ai-run-log-item" key={log.key}>
                  <Tag color={log.status === 'ok' ? 'green' : log.status === 'error' ? 'red' : log.status === 'fallback' ? 'orange' : 'blue'}>
                    {log.status || 'running'}
                  </Tag>
                  {log.tool && <Text code>{log.tool}</Text>}
                  <Text>{log.message}</Text>
                </div>
              ))}
            </div>
          )}

          <div className="writer-ai-output" ref={aiOutputRef}>
            {aiMode === 'assistant' ? (
              assistantMessages.length > 0 ? (
                <div>
                  {assistantMessages.map((item, index) => (
                    <div key={`${item.role}-${index}`} className={`writer-ai-battle-turn writer-assistant-${item.role}`}>
                      <div className="writer-assistant-message-head">
                        <Tag color={item.role === 'user' ? 'default' : item.status === 'error' ? 'red' : item.status === 'aborted' ? 'orange' : 'blue'}>
                          {item.role === 'user' ? '你' : item.status === 'aborted' ? '已停止' : '自动助手'}
                        </Tag>
                        {item.role === 'user' && item.id && !aiGenerating && (
                          <Button
                            type="text"
                            size="small"
                            icon={<EditOutlined />}
                            onClick={() => editAssistantUserMessage(item)}
                          >
                            修改
                          </Button>
                        )}
                      </div>
                      <Paragraph style={{ marginTop: 4, marginBottom: 6, whiteSpace: 'pre-wrap' }}>{item.content}</Paragraph>
                      {item.data && (
                        <Space direction="vertical" size={6} style={{ width: '100%' }}>
                          {item.data.tool_logs?.length > 0 && (
                            <div className="writer-assistant-tools">
                              <Text type="secondary" style={{ fontSize: 12 }}>工具调用：</Text>
                              {item.data.tool_logs.map((log, logIndex) => (
                                <div className="writer-assistant-tool-row" key={`${log.tool}-${logIndex}`}>
                                  <Tag color={log.status === 'ok' ? 'green' : log.status === 'error' ? 'red' : log.status === 'fallback' ? 'orange' : log.status === 'running' ? 'blue' : 'default'}>
                                    {log.status}
                                  </Tag>
                                  <Text code>{log.tool}</Text>
                                  {log.detail && <Text type="secondary">{log.detail}</Text>}
                                </div>
                              ))}
                            </div>
                          )}
                          {item.data.issues?.length > 0 && (
                            <div>
                              <Text type="secondary" style={{ fontSize: 12 }}>问题：</Text>
                              {item.data.issues.map((issue, issueIndex) => <Paragraph key={issueIndex} style={{ marginBottom: 2 }}>{issue}</Paragraph>)}
                            </div>
                          )}
                          {item.data.suggestions?.length > 0 && (
                            <div>
                              <Text type="secondary" style={{ fontSize: 12 }}>建议：</Text>
                              {item.data.suggestions.map((suggestion, suggestionIndex) => <Paragraph key={suggestionIndex} style={{ marginBottom: 2 }}>{suggestion}</Paragraph>)}
                            </div>
                          )}
                          {item.data.roleplay_results?.some((result) => result.should_act) && (
                            <div>
                              <Text type="secondary" style={{ fontSize: 12 }}>角色行动：</Text>
                              {item.data.roleplay_results.filter((result) => result.should_act).map((result) => (
                                <Paragraph key={result.character_id} style={{ marginBottom: 2 }}>
                                  <Text strong>{result.character_name}：</Text>{result.content}
                                </Paragraph>
                              ))}
                            </div>
                          )}
                          {item.data.worldbuilding_suggestions?.length > 0 && (
                            <div>
                              <Text type="secondary" style={{ fontSize: 12 }}>建议补充设定：</Text>
                              {item.data.worldbuilding_suggestions.map((entry, entryIndex) => (
                                <Paragraph key={`${entry.title}-${entryIndex}`} style={{ marginBottom: 4 }}>
                                  <Text strong>{entry.title}</Text>：{entry.content}
                                </Paragraph>
                              ))}
                            </div>
                          )}
                          {item.data.chapter_draft?.content && (
                            <div>
                              <Text type="secondary" style={{ fontSize: 12 }}>章节草稿：</Text>
                              <Paragraph style={{ marginBottom: 4 }}><Text strong>{item.data.chapter_draft.title || '未命名章节'}</Text></Paragraph>
                              <Paragraph ellipsis={{ rows: 5, expandable: true, symbol: '展开' }} style={{ whiteSpace: 'pre-wrap' }}>
                                {item.data.chapter_draft.content}
                              </Paragraph>
                            </div>
                          )}
                          {item.data.created_chapter && (
                            <Tag color="green">已创建章节：{item.data.created_chapter.title}</Tag>
                          )}
                        </Space>
                      )}
                    </div>
                  ))}
                  {aiGenerating && <Text type="secondary">自动助手正在读取资料并思考...</Text>}
                </div>
              ) : aiGenerating ? (
                <Text type="secondary">自动助手正在读取资料并思考...</Text>
              ) : (
                <Text type="secondary">可以直接提出剧情需求，助手会自动读取摘要、角色、世界观和章节正文。</Text>
              )
            ) : aiMode === 'battle' ? (
              aiBattleDialogue.length > 0 ? (
                <div>
                  {aiBattleDialogue.map((d, i) => (
                    <div key={i} className="writer-ai-battle-turn">
                      <Tag color="blue">{d.character_name}</Tag>
                      <Paragraph style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{d.content || (aiGenerating && i === aiBattleDialogue.length - 1 ? '生成中...' : '')}</Paragraph>
                    </div>
                  ))}
                </div>
              ) : aiGenerating ? (
                <Text type="secondary">等待角色发言...</Text>
              ) : (
                <Text type="secondary">对戏对话将显示在这里</Text>
              )
            ) : aiMode === 'conflict' ? (
              aiConflicts.length > 0 ? (
                <div>
                  {aiConflicts.map((c, i) => {
                    const typeLabel: Record<string, string> = { personality: '人物冲突', faction: '势力冲突', inner: '内心冲突' }
                    const tensionColor: Record<string, string> = { low: 'green', medium: 'orange', high: 'red' }
                    return (
                      <div key={i} className="writer-ai-battle-turn" style={{ borderLeftColor: tensionColor[c.tension_level] || '#1677ff' }}>
                        <Space size={4} wrap style={{ marginBottom: 4 }}>
                          <Tag color={c.type === 'personality' ? 'blue' : c.type === 'faction' ? 'purple' : 'gold'}>
                            {typeLabel[c.type] || c.type}
                          </Tag>
                          <Tag color={tensionColor[c.tension_level] || 'default'}>
                            {c.tension_level === 'high' ? '高张力' : c.tension_level === 'medium' ? '中张力' : '低张力'}
                          </Tag>
                        </Space>
                        <Text strong style={{ display: 'block', marginBottom: 4 }}>{c.title}</Text>
                        <Paragraph style={{ marginBottom: 6, whiteSpace: 'pre-wrap' }}>{c.description}</Paragraph>
                        {c.involved_characters && c.involved_characters.length > 0 && (
                          <Paragraph style={{ marginBottom: 4 }}>
                            <Text type="secondary">涉及角色：</Text>
                            {c.involved_characters.map((name) => (
                              <Tag key={name} style={{ marginBottom: 2 }}>{name}</Tag>
                            ))}
                          </Paragraph>
                        )}
                        {c.suggested_outcome && (
                          <Paragraph style={{ marginBottom: 0 }}>
                            <Text type="secondary">建议走向：{c.suggested_outcome}</Text>
                          </Paragraph>
                        )}
                        <Button
                          size="small"
                          type="primary"
                          icon={<PlusOutlined />}
                          loading={adoptingConflictIndex === i}
                          onClick={() => handleAdoptConflict(c, i)}
                        >
                          采纳并创建大纲节点
                        </Button>
                      </div>
                    )
                  })}
                </div>
              ) : aiGenerating ? (
                <Text type="secondary">分析剧情冲突中...</Text>
              ) : (
                <Text type="secondary">点击"生成"分析当前剧情的冲突建议</Text>
              )
            ) : (
              aiOutput ? (
                <Paragraph style={{ whiteSpace: 'pre-wrap' }}>{aiOutput}</Paragraph>
              ) : aiGenerating ? (
                <Text type="secondary">生成中...</Text>
              ) : (
                <Text type="secondary">AI生成结果将显示在这里</Text>
              )
            )}
          </div>

          {aiMode === 'assistant' && (
            <div className="writer-assistant-composer">
              {editingAssistantMessageId && (
                <div className="writer-assistant-editing">
                  <Text type="secondary">正在修改已发送的消息，发送后会从这里重新生成后续回复。</Text>
                  <Button type="link" size="small" onClick={cancelAssistantEdit}>取消修改</Button>
                </div>
              )}
              <TextArea
                ref={(node: any) => { assistantInputRef.current = node?.resizableTextArea?.textArea || null }}
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder="和AI讨论剧情、检查矛盾、预测下一步，或让它自动调用角色AI写新章节..."
                autoSize={{ minRows: 2, maxRows: 6 }}
                disabled={aiGenerating}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleGenerate()
                }}
              />
              <div className="writer-assistant-composer-actions">
                <Text type="secondary" style={{ fontSize: 11 }}>Ctrl+Enter 发送</Text>
                {aiGenerating ? (
                  <Button danger icon={<StopOutlined />} onClick={handleStopGeneration}>停止</Button>
                ) : (
                  <Button type="primary" icon={<SendOutlined />} onClick={handleGenerate} disabled={!aiPrompt.trim()}>
                    发送
                  </Button>
                )}
              </div>
            </div>
          )}

          {((aiOutput || aiBattleDialogue.length > 0 || aiConflicts.length > 0) && !aiGenerating) && (
            <Space style={{ marginTop: 8 }} wrap>
              {aiMode !== 'conflict' ? (
                <>
                  <Button type="primary" icon={<SaveOutlined />} onClick={insertAiText}>插入正文</Button>
                  <Button onClick={replaceWithAiText}>替换选中</Button>
                </>
              ) : null}
              <Button onClick={clearAiOutput}>清除</Button>
            </Space>
          )}

          <div style={{ marginTop: 12, padding: 10, background: '#fafafa', borderRadius: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <Text strong style={{ fontSize: 12 }}><SettingOutlined /> 写作风格</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>Ctrl+Enter 生成</Text>
            </div>
            <Space direction="vertical" size={6} style={{ width: '100%' }}>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>叙事视角</Text>
                <Select
                  value={narrativePerspective}
                  onChange={(v) => { setNarrativePerspective(v); saveStyle(v, writingStyle) }}
                  loading={styleSaving}
                  size="small"
                  style={{ width: '100%' }}
                  options={[
                    { value: 'third_person', label: '第三人称' },
                    { value: 'first_person', label: '第一人称' },
                    { value: 'omniscient', label: '上帝视角' },
                  ]}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>文风偏好</Text>
                <Select
                  value={writingStyle}
                  onChange={(v) => { setWritingStyle(v); saveStyle(narrativePerspective, v) }}
                  loading={styleSaving}
                  size="small"
                  style={{ width: '100%' }}
                  options={[
                    { value: 'natural', label: '自然' },
                    { value: 'vivid', label: '华丽生动' },
                    { value: 'concise', label: '白描简洁' },
                    { value: 'serious', label: '严肃' },
                    { value: 'humorous', label: '幽默' },
                    { value: 'poetic', label: '诗意' },
                  ]}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>禁用句式（每行一条）</Text>
                <TextArea
                  value={forbiddenSentencePatterns}
                  onChange={(e) => setForbiddenSentencePatterns(e.target.value)}
                  onBlur={(e) => saveStyle(narrativePerspective, writingStyle, e.target.value, rhetoricGuidelines)}
                  autoSize={{ minRows: 3, maxRows: 6 }}
                  size="small"
                  placeholder={DEFAULT_FORBIDDEN_SENTENCE_PATTERNS}
                  disabled={styleSaving}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 2 }}>修辞限制</Text>
                <TextArea
                  value={rhetoricGuidelines}
                  onChange={(e) => setRhetoricGuidelines(e.target.value)}
                  onBlur={(e) => saveStyle(narrativePerspective, writingStyle, forbiddenSentencePatterns, e.target.value)}
                  autoSize={{ minRows: 3, maxRows: 6 }}
                  size="small"
                  placeholder={DEFAULT_RHETORIC_GUIDELINES}
                  disabled={styleSaving}
                />
              </div>
              <Button
                size="small"
                onClick={() => {
                  setForbiddenSentencePatterns(DEFAULT_FORBIDDEN_SENTENCE_PATTERNS)
                  setRhetoricGuidelines(DEFAULT_RHETORIC_GUIDELINES)
                  saveStyle(narrativePerspective, writingStyle, DEFAULT_FORBIDDEN_SENTENCE_PATTERNS, DEFAULT_RHETORIC_GUIDELINES)
                }}
              >
                恢复默认表达限制
              </Button>
            </Space>
          </div>
          </div>
          )}
        </aside>
        )}
      </div>
    </div>
  )
}

export default WriterPage

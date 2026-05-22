import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Button,
  Empty,
  Input,
  InputNumber,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
  Popconfirm,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  ApartmentOutlined,
  CloseOutlined,
  DeleteOutlined,
  EditOutlined,
  EnvironmentOutlined,
  GlobalOutlined,
  HistoryOutlined,
  PlusOutlined,
  ReloadOutlined,
  SaveOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons'
import { apiClient } from '../api/client'
import WorkspaceAssistantChat from '../components/WorkspaceAssistantChat'
import { useModelOptions } from '../hooks/useModelOptions'
import './WorldbuildingPage.css'

const { Paragraph, Text, Title } = Typography

type Dimension = 'geography' | 'history' | 'factions' | 'power_system' | 'races' | 'culture'

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface WorldbuildingEntry {
  id: string
  project_id: string
  dimension: Dimension
  title: string
  content: string
  sort_order: number
  created_at: string
  updated_at: string
}

interface WorldbuildingListResponse {
  grouped: Record<Dimension, WorldbuildingEntry[]>
  total: number
}

interface ConflictItem {
  entry_a_id: string
  entry_b_id: string
  dimension?: Dimension
  severity: 'low' | 'medium' | 'high' | string
  summary: string
  detail: string
}

interface ConflictResponse {
  items: ConflictItem[]
  total: number
  analysis?: string
}

interface DraftEntry {
  title: string
  content: string
  sort_order: number
}

interface WorldbuildingPageProps {
  projectId: string
}

interface AIRunLog {
  key: string
  tool?: string
  status?: string
  message: string
}

const NEW_ROW_ID = '__new__'

const DIMENSIONS: Array<{ key: Dimension; label: string; icon: JSX.Element }> = [
  { key: 'geography', label: '地理', icon: <EnvironmentOutlined /> },
  { key: 'history', label: '历史', icon: <HistoryOutlined /> },
  { key: 'factions', label: '势力', icon: <TeamOutlined /> },
  { key: 'power_system', label: '规则体系', icon: <ThunderboltOutlined /> },
  { key: 'races', label: '种族', icon: <ApartmentOutlined /> },
  { key: 'culture', label: '文化', icon: <GlobalOutlined /> },
]

const EMPTY_GROUPED = DIMENSIONS.reduce((acc, item) => {
  acc[item.key] = []
  return acc
}, {} as Record<Dimension, WorldbuildingEntry[]>)

function WorldbuildingPage({ projectId }: WorldbuildingPageProps) {
  const [activeDimension, setActiveDimension] = useState<Dimension>('geography')
  const [entriesByDimension, setEntriesByDimension] = useState<Record<Dimension, WorldbuildingEntry[]>>({
    ...EMPTY_GROUPED,
  })
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState<DraftEntry>({ title: '', content: '', sort_order: 0 })

  const [aiDimension, setAiDimension] = useState<Dimension>('geography')
  const [aiConcept, setAiConcept] = useState('')
  const [aiSuggestion, setAiSuggestion] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiModel, setAiModel] = useState<string | undefined>()
  const [aiRunLogs, setAiRunLogs] = useState<AIRunLog[]>([])
  const { modelOptions, defaultModel, loading: modelsLoading } = useModelOptions()

  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [conflictLoading, setConflictLoading] = useState(false)

  const fetchEntries = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<WorldbuildingListResponse>>(
        `/projects/${projectId}/worldbuilding`
      )
      setEntriesByDimension({ ...EMPTY_GROUPED, ...res.data.data.grouped })
    } catch (err: any) {
      message.error(err.message || '获取世界观条目失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchEntries()
  }, [fetchEntries])

  useEffect(() => {
    if (!aiModel && defaultModel) {
      setAiModel(defaultModel)
    }
  }, [aiModel, defaultModel])

  const currentEntries = entriesByDimension[activeDimension] || []

  const conflictEntryIds = useMemo(() => {
    const ids = new Set<string>()
    conflicts.forEach((item) => {
      ids.add(item.entry_a_id)
      ids.add(item.entry_b_id)
    })
    return ids
  }, [conflicts])

  const startCreate = () => {
    const nextSortOrder = currentEntries.length
    setCreating(true)
    setEditingId(NEW_ROW_ID)
    setDraft({ title: '', content: '', sort_order: nextSortOrder })
  }

  const startEdit = (entry: WorldbuildingEntry) => {
    setCreating(false)
    setEditingId(entry.id)
    setDraft({
      title: entry.title,
      content: entry.content,
      sort_order: entry.sort_order,
    })
  }

  const cancelEdit = () => {
    setCreating(false)
    setEditingId(null)
    setDraft({ title: '', content: '', sort_order: 0 })
  }

  const saveDraft = async () => {
    if (!draft.title.trim()) {
      message.warning('请输入条目标题')
      return
    }
    if (!draft.content.trim()) {
      message.warning('请输入条目内容')
      return
    }

    setSaving(true)
    try {
      const payload = {
        dimension: activeDimension,
        title: draft.title.trim(),
        content: draft.content.trim(),
        sort_order: draft.sort_order,
      }

      if (creating) {
        await apiClient.post(`/projects/${projectId}/worldbuilding`, payload)
        message.success('世界观条目已创建')
      } else if (editingId) {
        await apiClient.put(`/projects/${projectId}/worldbuilding/${editingId}`, payload)
        message.success('世界观条目已保存')
      }

      cancelEdit()
      fetchEntries()
    } catch (err: any) {
      message.error(err.message || '保存世界观条目失败')
    } finally {
      setSaving(false)
    }
  }

  const deleteEntry = async (entryId: string) => {
    try {
      await apiClient.delete(`/projects/${projectId}/worldbuilding/${entryId}`)
      message.success('世界观条目已删除')
      setConflicts((items) => items.filter((item) => item.entry_a_id !== entryId && item.entry_b_id !== entryId))
      fetchEntries()
    } catch (err: any) {
      message.error(err.message || '删除世界观条目失败')
    }
  }

  const generateSuggestion = async () => {
    if (!aiConcept.trim()) {
      message.warning('请输入概念或关键词')
      return
    }
    setAiLoading(true)
    setAiSuggestion('')
    setAiRunLogs([{
      key: `${Date.now()}-start`,
      tool: 'worldbuilding_context',
      status: 'running',
      message: `正在读取${DIMENSIONS.find((item) => item.key === aiDimension)?.label || aiDimension}维度已有设定`,
    }])
    try {
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-model`,
        tool: 'worldbuilding_ai',
        status: 'running',
        message: `正在调用模型：${aiModel || defaultModel || '默认模型'}`,
      }])
      const res = await apiClient.post<ApiResponse<{
        suggestion: string
        dimension: Dimension
        concept: string
      }>>(`/projects/${projectId}/worldbuilding/ai-expand`, {
        dimension: aiDimension,
        concept: aiConcept.trim(),
        model: aiModel || defaultModel || undefined,
      })
      setAiSuggestion(res.data.data.suggestion)
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-done`,
        tool: 'worldbuilding_ai',
        status: 'ok',
        message: '世界观扩展建议已生成',
      }])
    } catch (err: any) {
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-error`,
        tool: 'worldbuilding_ai',
        status: 'error',
        message: err.message || 'AI 扩展失败',
      }])
      message.error(err.message || 'AI 扩展失败，请检查模型配置')
    } finally {
      setAiLoading(false)
    }
  }

  const useSuggestionAsDraft = () => {
    if (!aiSuggestion.trim()) return
    setActiveDimension(aiDimension)
    setCreating(true)
    setEditingId(NEW_ROW_ID)
    setDraft({
      title: aiConcept.trim() || 'AI 设定建议',
      content: aiSuggestion.trim(),
      sort_order: (entriesByDimension[aiDimension] || []).length,
    })
  }

  const detectConflicts = async () => {
    setConflictLoading(true)
    setAiRunLogs([{
      key: `${Date.now()}-conflict-start`,
      tool: 'worldbuilding_conflicts',
      status: 'running',
      message: '正在读取全部世界观条目并检查矛盾',
    }])
    try {
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-conflict-model`,
        tool: 'worldbuilding_conflicts',
        status: 'running',
        message: `正在调用模型：${aiModel || defaultModel || '默认模型'}`,
      }])
      const res = await apiClient.get<ApiResponse<ConflictResponse>>(
        `/projects/${projectId}/worldbuilding/conflicts`,
        { model: aiModel || defaultModel || undefined },
      )
      const items = res.data.data.items || []
      setConflicts(items)
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-conflict-done`,
        tool: 'worldbuilding_conflicts',
        status: 'ok',
        message: `矛盾检查完成，发现 ${items.length} 处`,
      }])
      if (items.length > 0) {
        message.warning(`检测到 ${items.length} 处可能的设定矛盾`)
      } else {
        message.success('暂未检测到明显设定矛盾')
      }
    } catch (err: any) {
      setAiRunLogs((prev) => [...prev, {
        key: `${Date.now()}-conflict-error`,
        tool: 'worldbuilding_conflicts',
        status: 'error',
        message: err.message || '矛盾检测失败',
      }])
      message.error(err.message || '矛盾检测失败，请检查模型配置')
    } finally {
      setConflictLoading(false)
    }
  }

  const dataSource = creating
    ? [
        {
          id: NEW_ROW_ID,
          project_id: projectId,
          dimension: activeDimension,
          title: '',
          content: '',
          sort_order: draft.sort_order,
          created_at: '',
          updated_at: '',
        } as WorldbuildingEntry,
        ...currentEntries,
      ]
    : currentEntries

  const columns: ColumnsType<WorldbuildingEntry> = [
    {
      title: '条目',
      dataIndex: 'title',
      width: 220,
      render: (_value, record) => {
        const isEditing = editingId === record.id
        if (isEditing) {
          return (
            <Input
              value={draft.title}
              onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
              placeholder="例如：北境雪原"
              maxLength={200}
            />
          )
        }
        return (
          <Space size={8}>
            {conflictEntryIds.has(record.id) && <WarningOutlined style={{ color: '#fa8c16' }} />}
            <Text strong>{record.title}</Text>
          </Space>
        )
      },
    },
    {
      title: '内容',
      dataIndex: 'content',
      render: (_value, record) => {
        const isEditing = editingId === record.id
        if (isEditing) {
          return (
            <Input.TextArea
              value={draft.content}
              onChange={(event) => setDraft((prev) => ({ ...prev, content: event.target.value }))}
              placeholder="写下这条设定的规则、历史、限制与剧情钩子"
              autoSize={{ minRows: 3, maxRows: 8 }}
              showCount
            />
          )
        }
        return (
          <Paragraph ellipsis={{ rows: 2, expandable: true, symbol: '展开' }} style={{ marginBottom: 0 }}>
            {record.content}
          </Paragraph>
        )
      },
    },
    {
      title: '排序',
      dataIndex: 'sort_order',
      width: 96,
      render: (_value, record) => {
        const isEditing = editingId === record.id
        if (isEditing) {
          return (
            <InputNumber
              min={0}
              value={draft.sort_order}
              onChange={(value) => setDraft((prev) => ({ ...prev, sort_order: Number(value || 0) }))}
              style={{ width: 72 }}
            />
          )
        }
        return record.sort_order
      },
    },
    {
      title: '更新',
      dataIndex: 'updated_at',
      width: 130,
      render: (value: string) => (value ? new Date(value).toLocaleDateString('zh-CN') : '新建中'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_value, record) => {
        const isEditing = editingId === record.id
        if (isEditing) {
          return (
            <Space size={4}>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                size="small"
                loading={saving}
                onClick={saveDraft}
              />
              <Button icon={<CloseOutlined />} size="small" onClick={cancelEdit} />
            </Space>
          )
        }
        return (
          <Space size={4}>
            <Button
              icon={<EditOutlined />}
              size="small"
              onClick={() => startEdit(record)}
              disabled={!!editingId}
            />
            <Popconfirm
              title="删除条目"
              description="确定删除这条世界观设定吗？"
              okText="删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
              onConfirm={() => deleteEntry(record.id)}
            >
              <Button icon={<DeleteOutlined />} size="small" danger disabled={!!editingId} />
            </Popconfirm>
          </Space>
        )
      },
    },
  ]

  void setAiDimension
  void setAiConcept
  void aiLoading
  void aiRunLogs
  void generateSuggestion
  void useSuggestionAsDraft

  return (
    <div className="worldbuilding-page">
      <div className="worldbuilding-shell">
        <section className="worldbuilding-main">
          <div className="worldbuilding-toolbar">
            <Title level={4} style={{ margin: 0 }}>世界观</Title>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchEntries} loading={loading}>
                刷新
              </Button>
              <Button icon={<WarningOutlined />} onClick={detectConflicts} loading={conflictLoading}>
                检测矛盾
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={startCreate} disabled={!!editingId}>
                新增条目
              </Button>
            </Space>
          </div>

          <Tabs
            activeKey={activeDimension}
            onChange={(key) => setActiveDimension(key as Dimension)}
            style={{ padding: '0 16px 16px' }}
            items={DIMENSIONS.map((dimension) => ({
              key: dimension.key,
              label: (
                <Space size={6}>
                  {dimension.icon}
                  {dimension.label}
                  <Tag>{entriesByDimension[dimension.key]?.length || 0}</Tag>
                </Space>
              ),
              children: (
                <Table
                  rowKey="id"
                  columns={columns}
                  dataSource={dataSource}
                  loading={loading}
                  pagination={false}
                  rowClassName={(record) => (conflictEntryIds.has(record.id) ? 'worldbuilding-row-conflict' : '')}
                  locale={{
                    emptyText: (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无条目"
                      >
                        <Button type="primary" icon={<PlusOutlined />} onClick={startCreate}>
                          新增条目
                        </Button>
                      </Empty>
                    ),
                  }}
                />
              ),
            }))}
          />
        </section>

        <aside className="worldbuilding-side">
          <WorkspaceAssistantChat
            projectId={projectId}
            scope="project"
            model={aiModel}
            defaultModel={defaultModel}
            modelOptions={modelOptions}
            modelsLoading={modelsLoading}
            onModelChange={setAiModel}
            onApplied={fetchEntries}
          />
        </aside>
      </div>
    </div>
  )
}

export default WorldbuildingPage

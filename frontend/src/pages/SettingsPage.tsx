import { useState, useEffect, useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import {
  Card,
  Typography,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  message,
  Space,
  Divider,
  Descriptions,
  Collapse,
  InputNumber,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  GlobalOutlined,
  ReloadOutlined,
  ArrowLeftOutlined,
  HomeOutlined,
} from '@ant-design/icons'
import { apiClient } from '../api/client'
import { useAppStore } from '../stores'

const { Title, Text } = Typography

interface ModelConfig {
  id: string
  provider: string
  default_model: string
  is_global_default: boolean
  base_url_override?: string
  max_output_tokens?: number | null
  effective_max_output_tokens?: number
  deconstruct_input_char_limit?: number | null
  effective_deconstruct_input_char_limit?: number
  deconstruct_item_char_limit?: number | null
  effective_deconstruct_item_char_limit?: number
  api_key_masked?: string
  created_at?: string
  updated_at?: string
}

interface GlobalModel {
  provider: string | null
  model: string | null
}

interface ModelOption {
  id: string
  display_name?: string
}

const PROVIDER_OPTIONS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic Claude' },
  { value: 'deepseek', label: 'DeepSeek（v4-pro / v4-flash）' },
  { value: 'qwen', label: '通义千问' },
]

const PROVIDER_LABEL_MAP: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic Claude',
  deepseek: 'DeepSeek',
  qwen: '通义千问',
}

const PROVIDER_COLOR_MAP: Record<string, string> = {
  openai: 'green',
  anthropic: 'purple',
  deepseek: 'blue',
  qwen: 'orange',
}

const DEEPSEEK_MODEL_OPTIONS: ModelOption[] = [
  { id: 'deepseek-v4-pro', display_name: 'deepseek-v4-pro' },
  { id: 'deepseek-v4-flash', display_name: 'deepseek-v4-flash' },
]

const FALLBACK_OUTPUT_LIMIT = 16000
const MODEL_OUTPUT_LIMITS: Record<string, number> = {
  'deepseek:deepseek-v4-pro': 384000,
  'deepseek:deepseek-v4-flash': 384000,
}
const PROVIDER_OUTPUT_LIMITS: Record<string, number> = {
  deepseek: 384000,
}

const fallbackModelOptions = (provider?: string): ModelOption[] => (
  provider === 'deepseek' ? DEEPSEEK_MODEL_OPTIONS : []
)

const normalizeDefaultModel = (provider: string, model: string) => {
  if (provider === 'deepseek' && model === 'deepseek-v3') {
    return 'deepseek-v4-flash'
  }
  return model
}

const isDeepSeekModelSupported = (model: string) => (
  DEEPSEEK_MODEL_OPTIONS.some((option) => option.id === model)
)

const normalizeProviderModelOptions = (provider: string, options: ModelOption[]) => {
  if (provider !== 'deepseek') return options
  const normalized = options
    .map((option) => ({
      id: normalizeDefaultModel(provider, option.id),
      display_name: normalizeDefaultModel(provider, option.display_name || option.id),
    }))
    .filter((option) => isDeepSeekModelSupported(option.id))
  const unique = Array.from(new Map(normalized.map((option) => [option.id, option])).values())
  return unique.length > 0 ? unique : DEEPSEEK_MODEL_OPTIONS
}

const defaultOutputLimit = (provider?: string, model?: string) => {
  if (!provider) return FALLBACK_OUTPUT_LIMIT
  const key = `${provider}:${model || ''}`
  return MODEL_OUTPUT_LIMITS[key] || PROVIDER_OUTPUT_LIMITS[provider] || FALLBACK_OUTPUT_LIMIT
}

const defaultSafetyLimits = (provider?: string, model?: string) => {
  const limit = defaultOutputLimit(provider, model)
  return {
    max_output_tokens: limit,
    deconstruct_input_char_limit: limit,
    deconstruct_item_char_limit: limit,
  }
}

const AI_PROMPT_PRESETS = [
  {
    key: 'narrator',
    label: '叙述者写作',
    prompt: '你是一位专业的小说叙述者AI，负责场景描写、气氛渲染、动作刻画和剧情推进。你的写作风格应遵循作品设定、禁用句式和修辞限制，与既有世界观和角色设定保持一致。只输出叙述文本，避免元评论，直接输出正文。',
  },
  {
    key: 'character',
    label: '角色对话',
    prompt: '你是小说中的指定角色。请以该角色的身份、性格、说话风格生成对话或内心独白，始终保持在角色内，结合角色档案、AI对话参数、关系网络、近期经历、当前大纲和前文摘要。',
  },
  {
    key: 'battle',
    label: '多角色对戏',
    prompt: '你是当前回合发言角色。请基于场景、世界观、当前大纲、在场角色、关系网络、前序对话历史和角色近期经历做出连贯回应，只输出该角色的对话或行为。',
  },
  {
    key: 'outline',
    label: '大纲建议',
    prompt: '你是小说写作AI Agent的大纲策划助手。请输出中文剧情摘要，强调冲突、行动、转折和悬念，保持与既有世界观和角色设定一致，不输出Markdown表格。',
  },
  {
    key: 'worldbuilding',
    label: '世界观扩展',
    prompt: '你是小说写作AI Agent的叙述者世界观编辑。请帮助作者扩展设定，保持逻辑自洽、可用于后续剧情写作，输出具体可落地的中文细节，避免空泛建议。',
  },
  {
    key: 'conflict',
    label: '情节冲突',
    prompt: '你是小说情节冲突设计顾问。请根据当前剧情状态分析并提供人物冲突、势力冲突、内心冲突等建议，只输出包含类型、标题、描述、涉及角色、张力等级和建议走向的JSON。',
  },
  {
    key: 'rewrite',
    label: '改写/扩写/续写',
    prompt: '你是专业小说文本操作助手。改写时保留核心含义并改变表达；扩写时保留原文并增加环境、动作、心理或背景细节；续写时承接上文风格、禁用句式、修辞限制和剧情逻辑。',
  },
  {
    key: 'character-evolution',
    label: '角色演进检测',
    prompt: '你是小说角色设定追踪助手。请分析新章节内容，检测角色发生的技能、经历、关系、性格变化，只输出结构化JSON数组；没有明显变化时输出空数组。',
  },
  {
    key: 'import-deconstruct',
    label: '导入校正/拆书',
    prompt: '导入校正用于校验章节边界，输出章节标题和全文字符位置。拆书Map阶段分析角色、事件、节奏、爽点和技法；Reduce阶段聚合大纲结构、角色频率、情节节点和节奏曲线。',
  },
]

function SettingsPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { projects, fetchProjects } = useAppStore()
  const [configs, setConfigs] = useState<ModelConfig[]>([])
  const [globalModel, setGlobalModel] = useState<GlobalModel>({ provider: null, model: null })
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [globalForm] = Form.useForm()
  const modalProvider = Form.useWatch('provider', form)
  const globalSelectedProvider = Form.useWatch('provider', globalForm)

  const [modelOptions, setModelOptions] = useState<ModelOption[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [testingConnection, setTestingConnection] = useState(false)
  const [connectionTestResult, setConnectionTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const fromProjectId = (location.state as { fromProjectId?: string } | null)?.fromProjectId
  const returnProjectId = fromProjectId || projects[0]?.id

  const fetchConfigs = useCallback(async () => {
    setLoading(true)
    try {
      const res = await apiClient.get<{ code: number; data: { items: ModelConfig[] } }>('/config/models')
      setConfigs(res.data.data.items)
    } catch (err: any) {
      message.error(err.message || '获取模型配置失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchGlobalModel = useCallback(async () => {
    try {
      const res = await apiClient.get<{ code: number; data: GlobalModel }>('/config/global-model')
      setGlobalModel(res.data.data)
      if (res.data.data.provider && res.data.data.model) {
        globalForm.setFieldsValue({
          provider: res.data.data.provider,
          model: normalizeDefaultModel(res.data.data.provider, res.data.data.model),
        })
      }
    } catch (err: any) {
      // ignore if not set
    }
  }, [globalForm])

  useEffect(() => {
    fetchConfigs()
    fetchGlobalModel()
    fetchProjects()
  }, [fetchConfigs, fetchGlobalModel, fetchProjects])

  const handleAddOrEdit = (provider?: string) => {
    setConnectionTestResult(null)
    if (provider) {
      const cfg = configs.find((c) => c.provider === provider)
      if (cfg) {
        setEditingProvider(provider)
        const defaultModel = normalizeDefaultModel(cfg.provider, cfg.default_model)
        setModelOptions(fallbackModelOptions(cfg.provider))
        form.setFieldsValue({
          provider: cfg.provider,
          default_model: defaultModel,
          base_url_override: cfg.base_url_override || '',
          api_key: '',
          max_output_tokens: cfg.max_output_tokens || cfg.effective_max_output_tokens || defaultOutputLimit(cfg.provider, defaultModel),
          deconstruct_input_char_limit: cfg.deconstruct_input_char_limit || cfg.effective_deconstruct_input_char_limit || defaultOutputLimit(cfg.provider, defaultModel),
          deconstruct_item_char_limit: cfg.deconstruct_item_char_limit || cfg.effective_deconstruct_item_char_limit || defaultOutputLimit(cfg.provider, defaultModel),
        })
      }
    } else {
      setEditingProvider(null)
      setModelOptions([])
      form.resetFields()
    }
    setModalOpen(true)
  }

  const handleSubmit = async (values: any) => {
    try {
      const defaultModel = normalizeDefaultModel(values.provider, values.default_model)
      if (values.provider === 'deepseek' && !isDeepSeekModelSupported(defaultModel)) {
        message.error('DeepSeek 当前支持 deepseek-v4-pro 或 deepseek-v4-flash，请重新选择')
        return
      }
      await apiClient.post('/config/models', {
        provider: values.provider,
        api_key: values.api_key,
        default_model: defaultModel,
        base_url_override: values.base_url_override || null,
        max_output_tokens: values.max_output_tokens || null,
        deconstruct_input_char_limit: values.deconstruct_input_char_limit || null,
        deconstruct_item_char_limit: values.deconstruct_item_char_limit || null,
      })
      message.success('配置已保存')
      setModalOpen(false)
      form.resetFields()
      fetchConfigs()
    } catch (err: any) {
      message.error(err.message || '保存配置失败')
    }
  }

  const handleDelete = async (provider: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除 ${PROVIDER_LABEL_MAP[provider] || provider} 的配置吗？`,
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        try {
          await apiClient.delete(`/config/models/${provider}`)
          message.success('配置已删除')
          fetchConfigs()
          fetchGlobalModel()
        } catch (err: any) {
          message.error(err.message || '删除配置失败')
        }
      },
    })
  }

  const fetchModels = async () => {
    const provider = form.getFieldValue('provider')
    const apiKey = form.getFieldValue('api_key')
    if (!provider) return
    if (!apiKey) {
      setModelOptions(fallbackModelOptions(provider))
      return
    }

    setModelsLoading(true)
    setModelOptions(fallbackModelOptions(provider))
    try {
      const baseUrl = form.getFieldValue('base_url_override') || undefined
      const res = await apiClient.post<{ code: number; data: { models: ModelOption[] } }>(
        '/config/models/list',
        { provider, api_key: apiKey, base_url_override: baseUrl }
      )
      setModelOptions(normalizeProviderModelOptions(provider, res.data.data.models || []))
    } catch (err: any) {
      setModelOptions(fallbackModelOptions(provider))
    } finally {
      setModelsLoading(false)
    }
  }

  const testConnection = async () => {
    const provider = form.getFieldValue('provider')
    const apiKey = form.getFieldValue('api_key')
    if (!provider || !apiKey) {
      message.warning('请先选择提供商并输入 API Key')
      return
    }

    setTestingConnection(true)
    setConnectionTestResult(null)
    try {
      const baseUrl = form.getFieldValue('base_url_override') || undefined
      await apiClient.post('/config/models/test', {
        provider,
        api_key: apiKey,
        base_url_override: baseUrl,
      })
      setConnectionTestResult({ success: true, message: '连接成功，API Key 有效' })
    } catch (err: any) {
      setConnectionTestResult({ success: false, message: err.message || '连接失败' })
    } finally {
      setTestingConnection(false)
    }
  }

  const handleSetGlobal = async (values: { provider: string; model: string }) => {
    try {
      await apiClient.put('/config/global-model', {
        provider: values.provider,
        model: values.model,
      })
      message.success('全局默认模型已设置')
      fetchGlobalModel()
      fetchConfigs()
    } catch (err: any) {
      message.error(err.message || '设置全局默认模型失败')
    }
  }

  const columns = [
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      render: (v: string) => (
        <Tag color={PROVIDER_COLOR_MAP[v] || 'default'}>{PROVIDER_LABEL_MAP[v] || v}</Tag>
      ),
    },
    {
      title: '默认模型',
      dataIndex: 'default_model',
      key: 'default_model',
      render: (value: string, record: ModelConfig) => normalizeDefaultModel(record.provider, value),
    },
    {
      title: 'API Key',
      dataIndex: 'api_key_masked',
      key: 'api_key_masked',
      render: (v?: string) => v || '****',
    },
    {
      title: '全局默认',
      dataIndex: 'is_global_default',
      key: 'is_global_default',
      render: (v: boolean) =>
        v ? <Tag icon={<CheckCircleOutlined />} color="success">是</Tag> : <span>—</span>,
    },
    {
      title: '自定义端点',
      dataIndex: 'base_url_override',
      key: 'base_url_override',
      render: (v?: string) => v || '—',
    },
    {
      title: '安全长度',
      key: 'safety_limits',
      render: (_: any, record: ModelConfig) => (
        <Space size={4} wrap>
          <Tag>输出 {Number(record.effective_max_output_tokens || record.max_output_tokens || 0).toLocaleString()}</Tag>
          <Tag>合并输入 {Number(record.effective_deconstruct_input_char_limit || record.deconstruct_input_char_limit || 0).toLocaleString()}</Tag>
          <Tag>单条 {Number(record.effective_deconstruct_item_char_limit || record.deconstruct_item_char_limit || 0).toLocaleString()}</Tag>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: ModelConfig) => (
        <Space>
          <Button
            type="text"
            icon={<EditOutlined />}
            onClick={() => handleAddOrEdit(record.provider)}
          >
            编辑
          </Button>
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDelete(record.provider)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  const availableProvidersForGlobal = configs.map((c) => ({
    value: c.provider,
    label: PROVIDER_LABEL_MAP[c.provider] || c.provider,
    model: c.default_model,
  }))

  const availableModelsForGlobal = configs
    .filter((c) => !globalSelectedProvider || c.provider === globalSelectedProvider)
    .map((c) => ({
      value: normalizeDefaultModel(c.provider, c.default_model),
      label: `${PROVIDER_LABEL_MAP[c.provider] || c.provider} · ${normalizeDefaultModel(c.provider, c.default_model)}`,
    }))

  const defaultModelOptions = modelOptions.length > 0 ? modelOptions : fallbackModelOptions(modalProvider)

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <Title level={3} style={{ margin: 0 }}>⚙️ 系统设置</Title>
        <Space wrap>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => returnProjectId ? navigate(`/project/${returnProjectId}`) : navigate('/dashboard')}
          >
            返回作品
          </Button>
          <Button icon={<HomeOutlined />} onClick={() => navigate('/dashboard')}>
            作品管理
          </Button>
        </Space>
      </div>

      <Card
        title="模型提供商配置"
        style={{ marginTop: 16 }}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => handleAddOrEdit()}>
            添加配置
          </Button>
        }
      >
        <Table
          dataSource={configs}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{ emptyText: '暂无模型配置，请点击右上角添加' }}
        />
      </Card>

      <Card title={<span><GlobalOutlined /> 全局默认模型</span>} style={{ marginTop: 16 }}>
        {globalModel.provider ? (
          <Descriptions size="small" column={2} bordered>
            <Descriptions.Item label="当前全局默认提供商">
              <Tag color={PROVIDER_COLOR_MAP[globalModel.provider] || 'default'}>
                {PROVIDER_LABEL_MAP[globalModel.provider] || globalModel.provider}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="当前全局默认模型">
              {globalModel.provider && globalModel.model ? normalizeDefaultModel(globalModel.provider, globalModel.model) : globalModel.model}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <p style={{ color: '#999' }}>尚未设置全局默认模型</p>
        )}

        <Divider style={{ margin: '16px 0' }} />

        <Form
          form={globalForm}
          layout="inline"
          onFinish={handleSetGlobal}
        >
          <Form.Item
            name="provider"
            label="选择提供商"
            rules={[{ required: true, message: '请选择提供商' }]}
          >
            <Select
              style={{ width: 180 }}
              placeholder="选择提供商"
              options={availableProvidersForGlobal}
              onChange={(val) => {
                const cfg = configs.find((c) => c.provider === val)
                globalForm.setFieldsValue({ model: cfg ? normalizeDefaultModel(cfg.provider, cfg.default_model) : undefined })
              }}
            />
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名"
            rules={[{ required: true, message: '请选择模型名' }]}
          >
            <Select
              style={{ width: 240 }}
              placeholder="从已配置模型中选择"
              options={availableModelsForGlobal}
              optionFilterProp="label"
              showSearch
              notFoundContent="暂无已配置模型"
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">
              设为全局默认
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="AI提示词预设" style={{ marginTop: 16 }}>
        <Text type="secondary">
          这些是当前各AI模块使用的内置提示词摘要，便于核对每个模块的角色定位和输出约束。
        </Text>
        <Collapse
          size="small"
          style={{ marginTop: 12 }}
          items={AI_PROMPT_PRESETS.map((item) => ({
            key: item.key,
            label: item.label,
            children: (
              <Input.TextArea
                value={item.prompt}
                readOnly
                autoSize={{ minRows: 3, maxRows: 8 }}
              />
            ),
          }))}
        />
      </Card>

      <Modal
        title={editingProvider ? `编辑 ${PROVIDER_LABEL_MAP[editingProvider] || editingProvider} 配置` : '添加模型配置'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="provider"
            label="提供商"
            rules={[{ required: true, message: '请选择提供商' }]}
          >
            <Select
              placeholder="选择提供商"
              disabled={!!editingProvider}
              onChange={(provider) => {
                const fallback = fallbackModelOptions(provider)
                setModelOptions(fallback)
                setConnectionTestResult(null)
                const nextModel = fallback[0]?.id
                form.setFieldValue('default_model', nextModel)
                form.setFieldsValue(defaultSafetyLimits(provider, nextModel))
                if (form.getFieldValue('api_key')) {
                  fetchModels()
                }
              }}
              options={PROVIDER_OPTIONS}
            />
          </Form.Item>

          <Form.Item
            name="api_key"
            label={
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                API Key
                <Button
                  type="link"
                  size="small"
                  icon={<ReloadOutlined spin={testingConnection} />}
                  loading={testingConnection}
                  onClick={testConnection}
                  style={{ padding: 0 }}
                >
                  测试连接
                </Button>
              </span>
            }
            rules={[{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password
              placeholder="输入 API Key（将被加密存储）"
              onBlur={() => {
                if (form.getFieldValue('provider')) {
                  fetchModels()
                }
              }}
            />
          </Form.Item>

          {connectionTestResult && (
            <div style={{
              marginTop: -16, marginBottom: 16, fontSize: 13,
              color: connectionTestResult.success ? '#52c41a' : '#ff4d4f',
            }}>
              {connectionTestResult.success
                ? <CheckCircleOutlined />
                : <CloseCircleOutlined />
              }
              {' '}{connectionTestResult.message}
            </div>
          )}

          <Form.Item
            name="default_model"
            label="默认模型"
            rules={[{ required: true, message: '请选择默认模型名' }]}
          >
            <Select
              showSearch
              loading={modelsLoading}
              placeholder={
                modelsLoading
                  ? '正在获取模型列表...'
                  : defaultModelOptions.length > 0
                  ? '选择模型名'
                  : '请先输入 API Key 以获取模型列表'
              }
              notFoundContent={
                modelsLoading
                  ? '加载中...'
                  : form.getFieldValue('api_key')
                  ? '未找到模型'
                  : '请先输入 API Key'
              }
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              onChange={(modelName) => {
                const provider = form.getFieldValue('provider')
                form.setFieldsValue(defaultSafetyLimits(provider, modelName))
              }}
              options={defaultModelOptions.map((m) => ({
                value: m.id,
                label: m.display_name || m.id,
              }))}
            />
          </Form.Item>

          <Divider style={{ margin: '8px 0 16px' }} />

          <Form.Item
            name="max_output_tokens"
            label="模型最大输出 tokens"
            extra="默认按模型能力上限填充；DeepSeek v4-pro / v4-flash 默认为 384,000。"
            rules={[{ required: true, message: '请填写最大输出 tokens' }]}
          >
            <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="deconstruct_input_char_limit"
            label="拆书合并输入字符上限"
            extra="控制每次合并请求最多携带多少分块事实卡片内容。"
            rules={[{ required: true, message: '请填写合并输入字符上限' }]}
          >
            <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="deconstruct_item_char_limit"
            label="拆书单条内容字符上限"
            extra="控制单条事件、设定、角色字段的最大长度；超过后才会压缩。"
            rules={[{ required: true, message: '请填写单条内容字符上限' }]}
          >
            <InputNumber min={1} max={1000000} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="base_url_override"
            label="自定义 API 端点（可选）"
          >
            <Input placeholder="https://api.example.com/v1" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default SettingsPage

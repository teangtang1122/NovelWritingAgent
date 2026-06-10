import { Button, Radio, Space, Typography } from 'antd'
import { PlayCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import type { CatalogingMode } from './catalogingTypes'

const { Text, Title } = Typography

interface CatalogingHeaderProps {
  mode: CatalogingMode
  loading: boolean
  streaming: boolean
  onModeChange: (mode: CatalogingMode) => void
  onRefreshChapters: () => void
  onStartJob: () => void
}

function CatalogingHeader({
  mode,
  loading,
  streaming,
  onModeChange,
  onRefreshChapters,
  onStartJob,
}: CatalogingHeaderProps) {
  return (
    <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
      <div>
        <Title level={3} style={{ margin: 0 }}>作品建档</Title>
        <Text type="secondary">按章节顺序初始化章节摘要、大纲、角色状态和世界观时间线。</Text>
      </div>
      <Space>
        <Radio.Group value={mode} onChange={(event) => onModeChange(event.target.value)} buttonStyle="solid">
          <Radio.Button value="auto">自动</Radio.Button>
          <Radio.Button value="manual">手动确认</Radio.Button>
          <Radio.Button value="external_agent">外部 Agent / 无 API</Radio.Button>
        </Radio.Group>
        <Button icon={<ReloadOutlined />} onClick={onRefreshChapters}>刷新章节</Button>
        <Button type="primary" icon={<PlayCircleOutlined />} loading={loading || streaming} onClick={onStartJob}>
          开始建档
        </Button>
      </Space>
    </Space>
  )
}

export default CatalogingHeader

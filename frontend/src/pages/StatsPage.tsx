import { useCallback, useEffect, useState } from 'react'
import {
  Card,
  Col,
  Progress,
  Row,
  Select,
  Statistic,
  Table,
  Typography,
  message,
  InputNumber,
  Button,
  Space,
} from 'antd'
import {
  EditOutlined,
  FireOutlined,
  TrophyOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { apiClient } from '../api/client'

const { Title, Text } = Typography

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

interface TodayStats {
  date: string
  total_words: number
  daily_goal: number
  progress_percent: number
  chapters_written: number
}

interface DailyItem {
  date: string
  total_words: number
  daily_goal: number
}

interface HistoryStats {
  items: DailyItem[]
  total_days: number
  total_words: number
  average_words_per_day: number
}

interface StatsPageProps {
  projectId: string
}

function StatsPage({ projectId }: StatsPageProps) {
  const [today, setToday] = useState<TodayStats | null>(null)
  const [history, setHistory] = useState<HistoryStats | null>(null)
  const [historyDays, setHistoryDays] = useState(7)
  const [loading, setLoading] = useState(false)
  const [goalEditing, setGoalEditing] = useState(false)
  const [goalValue, setGoalValue] = useState(6000)

  const fetchToday = useCallback(async () => {
    try {
      const res = await apiClient.get<ApiResponse<TodayStats>>(`/projects/${projectId}/stats/today`)
      setToday(res.data.data)
      setGoalValue(res.data.data.daily_goal)
    } catch (err: any) {
      message.error(err.message || '获取今日统计失败')
    }
  }, [projectId])

  const fetchHistory = useCallback(async (days: number) => {
    setLoading(true)
    try {
      const res = await apiClient.get<ApiResponse<HistoryStats>>(`/projects/${projectId}/stats/history`, { days })
      setHistory(res.data.data)
    } catch (err: any) {
      message.error(err.message || '获取历史统计失败')
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    fetchToday()
    fetchHistory(historyDays)
  }, [fetchHistory, fetchToday, historyDays])

  const updateGoal = async () => {
    try {
      await apiClient.put(`/projects/${projectId}/stats/goal`, { daily_word_goal: goalValue })
      message.success('每日目标已更新')
      setGoalEditing(false)
      fetchToday()
    } catch (err: any) {
      message.error(err.message || '更新目标失败')
    }
  }

  const historyColumns = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      render: (v: string) => new Date(v).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', weekday: 'short' }),
    },
    {
      title: '字数',
      dataIndex: 'total_words',
      key: 'total_words',
      render: (v: number, record: DailyItem) => (
        <Space>
          <Text strong>{v.toLocaleString()}</Text>
          <Text type="secondary">/ {record.daily_goal.toLocaleString()}</Text>
        </Space>
      ),
    },
    {
      title: '完成度',
      key: 'progress',
      render: (_: unknown, record: DailyItem) => {
        const pct = record.daily_goal > 0 ? Math.min((record.total_words / record.daily_goal) * 100, 100) : 0
        return <Progress percent={Math.round(pct)} size="small" status={pct >= 100 ? 'success' : 'active'} style={{ width: 160 }} />
      },
    },
  ]

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginTop: 0 }}>
        <FireOutlined /> 写作统计
      </Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日字数"
              value={today?.total_words || 0}
              suffix="字"
              prefix={<EditOutlined />}
              valueStyle={{ color: (today?.total_words || 0) >= (today?.daily_goal || 6000) ? '#52c41a' : '#1677ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="每日目标"
              value={today?.daily_goal || 6000}
              suffix="字"
              prefix={<TrophyOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日进度"
              value={today?.progress_percent || 0}
              suffix="%"
              precision={1}
              prefix={<FireOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日更新章节"
              value={today?.chapters_written || 0}
              suffix="章"
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card style={{ marginBottom: 16 }}>
        <Progress
          percent={Math.min(today?.progress_percent || 0, 100)}
          status={(today?.progress_percent || 0) >= 100 ? 'success' : 'active'}
          strokeColor={{ '0%': '#1677ff', '100%': '#52c41a' }}
        />
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          {today ? (
            <Text type="secondary">
              {today.total_words.toLocaleString()} / {today.daily_goal.toLocaleString()} 字
              {(today?.progress_percent || 0) >= 100 ? ' — 目标达成！' : ''}
            </Text>
          ) : null}
        </div>
      </Card>

      <Card
        title={
          <Space>
            <span>修改每日目标</span>
            {goalEditing ? (
              <>
                <InputNumber min={0} step={500} value={goalValue} onChange={(v) => setGoalValue(v || 0)} style={{ width: 120 }} />
                <Button type="primary" size="small" onClick={updateGoal}>保存</Button>
                <Button size="small" onClick={() => setGoalEditing(false)}>取消</Button>
              </>
            ) : (
              <Button icon={<EditOutlined />} size="small" onClick={() => setGoalEditing(true)}>修改</Button>
            )}
          </Space>
        }
        style={{ marginBottom: 16 }}
      />

      <Card
        title="历史统计"
        extra={
          <Select value={historyDays} onChange={(v) => { setHistoryDays(v); fetchHistory(v) }} style={{ width: 140 }}>
            <Select.Option value={7}>最近 7 天</Select.Option>
            <Select.Option value={30}>最近 30 天</Select.Option>
            <Select.Option value={90}>最近 90 天</Select.Option>
          </Select>
        }
      >
        {history && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Statistic title="统计天数" value={history.total_days} suffix="天" />
            </Col>
            <Col span={8}>
              <Statistic title="累计字数" value={history.total_words.toLocaleString()} suffix="字" />
            </Col>
            <Col span={8}>
              <Statistic title="日均字数" value={history.average_words_per_day.toLocaleString()} suffix="字" />
            </Col>
          </Row>
        )}
        <Table
          dataSource={history?.items || []}
          columns={historyColumns}
          rowKey="date"
          loading={loading}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  )
}

export default StatsPage

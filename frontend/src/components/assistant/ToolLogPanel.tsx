/* Tool log panel for the assistant chat. */
import { Button, Space, Tag, Typography } from 'antd'
import { InfoCircleOutlined, ReloadOutlined } from '@ant-design/icons'
import type { WorkspaceAssistantRun, WorkspaceRunLog } from './types'

const { Text } = Typography

interface ToolLogPanelProps {
  logs: WorkspaceRunLog[]
  currentRun: WorkspaceAssistantRun | null
  showAll: boolean
  retryingStepId: string | null
  onToggleShowAll: () => void
  onRetryStep: (stepId: string, tool: string) => void
  onResumeFromStep: (stepId: string, tool: string) => void
  onShowDetail: (stepId: string) => void
}

export function ToolLogPanel({
  logs,
  currentRun,
  showAll,
  retryingStepId,
  onToggleShowAll,
  onRetryStep,
  onResumeFromStep,
  onShowDetail,
}: ToolLogPanelProps) {
  if (logs.length === 0) return null

  const visibleLogs = showAll ? logs : logs.slice(-5)

  return (
    <div className="workspace-assistant-run-logs">
      {logs.length > 5 && (
        <Button type="link" size="small" onClick={onToggleShowAll}>
          {showAll ? '收起日志' : `展开全部（${logs.length}）`}
        </Button>
      )}
      {visibleLogs.map((log) => (
        <div className="workspace-assistant-run-log-item" key={log.key}>
          <Tag
            color={
              log.status === 'ok' && log.resolvedStepId
                ? 'blue'
                : log.status === 'ok'
                  ? 'green'
                  : log.status === 'error' && log.resolvedStepId
                    ? 'green'
                    : log.status === 'error'
                      ? 'red'
                      : log.status === 'skipped'
                        ? 'orange'
                        : 'blue'
            }
          >
            {log.status === 'error' && log.resolvedStepId
              ? '已解决'
              : log.attemptNo && log.attemptNo > 1
                ? `重试 #${log.attemptNo}`
                : log.status || 'running'}
          </Tag>
          {log.tool && <Text code>{log.tool}</Text>}
          <Text>{log.message}</Text>
          {log.status === 'error' && !log.resolvedStepId && log.stepId && currentRun && (
            <Space size={4}>
              <Button
                type="link"
                size="small"
                icon={<ReloadOutlined />}
                loading={retryingStepId === log.stepId}
                disabled={retryingStepId !== null}
                onClick={() => onRetryStep(log.stepId!, log.tool || 'tool')}
                title="仅重试此步骤"
              >
                重试
              </Button>
              <Button
                type="link"
                size="small"
                loading={retryingStepId === log.stepId}
                disabled={retryingStepId !== null}
                onClick={() => onResumeFromStep(log.stepId!, log.tool || 'tool')}
                title="重试此步骤并继续后续步骤"
              >
                从这里继续
              </Button>
              <Button
                type="link"
                size="small"
                icon={<InfoCircleOutlined />}
                onClick={() => onShowDetail(log.stepId!)}
                title="查看详情"
              >
                详情
              </Button>
            </Space>
          )}
        </div>
      ))}
    </div>
  )
}

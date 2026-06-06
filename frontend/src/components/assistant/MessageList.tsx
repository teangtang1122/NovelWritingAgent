/* Message list rendering for the assistant chat. */
import { Empty, Space, Tag, Tooltip, Typography } from 'antd'
import { DownOutlined } from '@ant-design/icons'
import { ContextPreviewPanel } from '../ContextPreviewPanel'
import type { WorkspaceAssistantMessage, SkillMatch } from './types'
import { SCOPE_LABEL } from './constants'

const { Paragraph, Text } = Typography

interface MessageListProps {
  messages: WorkspaceAssistantMessage[]
  generating: boolean
  matchedSkills: SkillMatch[]
  showScrollBottom: boolean
  onScrollToBottom: () => void
  messagesRef: React.RefObject<HTMLDivElement>
  onScroll: () => void
}

export function MessageList({
  messages,
  generating,
  matchedSkills,
  showScrollBottom,
  onScrollToBottom,
  messagesRef,
  onScroll,
}: MessageListProps) {
  return (
    <>
      <div
        className="workspace-assistant-messages"
        ref={messagesRef}
        onScroll={onScroll}
      >
        {showScrollBottom && (
          <button
            type="button"
            className="workspace-assistant-scroll-bottom"
            onClick={onScrollToBottom}
            title="滚动到底部"
          >
            <DownOutlined />
          </button>
        )}

        {messages.length > 0 ? (
          messages.map((item, index) => (
            <div
              key={`${item.role}-${item.id || index}`}
              className={`workspace-assistant-message workspace-assistant-${item.role}`}
            >
              <Tag
                color={
                  item.role === 'user'
                    ? 'default'
                    : item.status === 'error'
                      ? 'red'
                      : item.status === 'aborted'
                        ? 'orange'
                        : 'blue'
                }
              >
                {item.role === 'user' ? '你' : SCOPE_LABEL}
              </Tag>
              <Paragraph style={{ marginTop: 6, marginBottom: 6, whiteSpace: 'pre-wrap' }}>
                {item.content}
              </Paragraph>

              {/* Context preview panels for chapter_writer / preview_writing_context */}
              {item.data?.applied_actions?.map((action, i) => {
                if (action.tool === 'chapter_writer' && action.data?.context_snapshot) {
                  return <ContextPreviewPanel key={`ctx-${i}`} snapshot={action.data.context_snapshot as any} />
                }
                if (action.tool === 'preview_writing_context' && action.data?.rag_sections) {
                  return (
                    <ContextPreviewPanel
                      key={`ctx-${i}`}
                      ragSections={action.data.rag_sections as any}
                      explanations={action.data.explanations as any}
                      warnings={action.data.warnings as any}
                      totalUsedChars={action.data.total_used_chars as number}
                      ragUsed={action.data.rag_used as boolean}
                    />
                  )
                }
                return null
              })}

              {/* Applied action tags */}
              {item.data?.applied_actions && item.data.applied_actions.length > 0 && (
                <Space wrap size={4}>
                  {item.data.applied_actions.map((action, actionIndex) => (
                    <Tag key={`${action.tool}-${actionIndex}`} color={action.status === 'ok' ? 'green' : 'orange'}>
                      {action.detail || action.tool}
                    </Tag>
                  ))}
                </Space>
              )}
            </div>
          ))
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="直接提出需求，AI会读取项目资料并决定是否调用工具。" />
        )}

        {generating && (
          <Text type="secondary">AI 助手正在分析{'...'}</Text>
        )}

        {/* Matched skills indicator */}
        {matchedSkills.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>已激活技能：</Text>
            <Space size={[4, 4]} wrap>
              {matchedSkills.map((s) => (
                <Tooltip
                  key={s.name}
                  title={s.truncated ? `${s.description || ''}（提示词已截断）` : s.description}
                >
                  <Tag color={s.injected === false ? 'default' : 'blue'} style={{ fontSize: 11 }}>
                    {s.name}{s.truncated ? ' ⚠' : ''}
                  </Tag>
                </Tooltip>
              ))}
            </Space>
          </div>
        )}
      </div>
    </>
  )
}

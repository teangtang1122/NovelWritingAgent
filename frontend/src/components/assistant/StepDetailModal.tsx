/* Step detail modal for the assistant chat. */
import { Modal, Typography } from 'antd'
import type { StepDetail } from './types'

const { Text } = Typography

interface StepDetailModalProps {
  detail: StepDetail | null
  onClose: () => void
}

export function StepDetailModal({ detail, onClose }: StepDetailModalProps) {
  return (
    <Modal
      title="步骤详情"
      open={!!detail}
      onCancel={onClose}
      footer={null}
      width={640}
    >
      {detail && (
        <div>
          <p><strong>步骤 ID：</strong>{detail.id}</p>
          <p><strong>工具：</strong>{detail.tool || '-'}</p>
          {detail.attempt_no && detail.attempt_no > 1 && (
            <p><strong>尝试次数：</strong>第 {detail.attempt_no} 次</p>
          )}
          {detail.request !== undefined && detail.request !== null && (
            <div>
              <Text strong>请求参数：</Text>
              <pre
                style={{
                  background: '#f5f5f5',
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 200,
                  overflow: 'auto',
                  fontSize: 12,
                }}
              >
                {JSON.stringify(detail.request, null, 2)}
              </pre>
            </div>
          )}
          {detail.result !== undefined && detail.result !== null && (
            <div>
              <Text strong>执行结果：</Text>
              <pre
                style={{
                  background: '#f5f5f5',
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 300,
                  overflow: 'auto',
                  fontSize: 12,
                }}
              >
                {JSON.stringify(detail.result, null, 2)}
              </pre>
            </div>
          )}
          {detail.error && (
            <div>
              <Text strong type="danger">错误信息：</Text>
              <pre
                style={{
                  background: '#fff2f0',
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 200,
                  overflow: 'auto',
                  fontSize: 12,
                  color: '#cf1322',
                }}
              >
                {detail.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}

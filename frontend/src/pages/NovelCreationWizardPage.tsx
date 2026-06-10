import { useState } from 'react'
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Steps,
  Typography,
  message,
} from 'antd'
import {
  BookOutlined,
  BulbOutlined,
  CheckCircleOutlined,
  EditOutlined,
} from '@ant-design/icons'

const { Title, Paragraph, Text } = Typography
const { TextArea } = Input

interface NovelCreationWizardPageProps {
  projectId: string
}

interface NovelBrief {
  genre: string
  target_audience: string
  platform: string
  user_brief: string
}

function NovelCreationWizardPage(_props: NovelCreationWizardPageProps) {
  const [currentStep, setCurrentStep] = useState(0)
  const [brief, setBrief] = useState<NovelBrief>({
    genre: '',
    target_audience: '',
    platform: '',
    user_brief: '',
  })
  const [sessionId] = useState<string | null>(null)

  const handleBriefSubmit = (values: NovelBrief) => {
    setBrief(values)
    setCurrentStep(1)
    message.info('需求已记录。请通过 MCP 工具或内部助手生成创意方案。')
  }

  const steps = [
    {
      title: '需求访谈',
      icon: <EditOutlined />,
      content: (
        <Card>
          <Paragraph>
            告诉我们你想写什么样的小说。填写越多信息，生成的创意方案越精准。
          </Paragraph>
          <Form
            layout="vertical"
            onFinish={handleBriefSubmit}
            initialValues={brief}
          >
            <Form.Item name="genre" label="小说类型">
              <Select placeholder="选择类型">
                <Select.Option value="xianxia">仙侠</Select.Option>
                <Select.Option value="urban">都市</Select.Option>
                <Select.Option value="scifi">科幻</Select.Option>
                <Select.Option value="fantasy">玄幻</Select.Option>
                <Select.Option value="mystery">悬疑</Select.Option>
                <Select.Option value="romance">言情</Select.Option>
                <Select.Option value="history">历史</Select.Option>
                <Select.Option value="other">其他</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="target_audience" label="目标读者">
              <Select placeholder="选择读者群">
                <Select.Option value="male">男频读者</Select.Option>
                <Select.Option value="female">女频读者</Select.Option>
                <Select.Option value="young">青少年</Select.Option>
                <Select.Option value="all">全年龄</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="platform" label="发布平台">
              <Select placeholder="选择平台">
                <Select.Option value="qidian">起点</Select.Option>
                <Select.Option value="tomato">番茄</Select.Option>
                <Select.Option value="jjwxc">晋江</Select.Option>
                <Select.Option value="zhihu">知乎</Select.Option>
                <Select.Option value="other">其他</Select.Option>
              </Select>
            </Form.Item>
            <Form.Item name="user_brief" label="创作方向">
              <TextArea
                rows={4}
                placeholder="你想写什么样的故事？核心卖点是什么？有什么特别的设定？"
              />
            </Form.Item>
            <Form.Item>
              <Button type="primary" htmlType="submit">
                下一步
              </Button>
            </Form.Item>
          </Form>
        </Card>
      ),
    },
    {
      title: '创意方案',
      icon: <BulbOutlined />,
      content: (
        <Card>
          <Paragraph>
            请通过 MCP 工具或内部助手生成创意方案。方案将显示在这里供你选择。
          </Paragraph>
          <Text type="secondary">
            使用工具：draft_novel_blueprint（session_id: {sessionId || '待创建'}）
          </Text>
        </Card>
      ),
    },
    {
      title: '评审与应用',
      icon: <CheckCircleOutlined />,
      content: (
        <Card>
          <Paragraph>
            评审创意方案并应用到项目。创建完成后将自动生成世界观、角色和大纲。
          </Paragraph>
          <Text type="secondary">
            使用工具：review_novel_blueprint → apply_novel_blueprint
          </Text>
        </Card>
      ),
    },
  ]

  return (
    <div style={{ padding: 24 }}>
      <Title level={4}>
        <BookOutlined style={{ marginRight: 8 }} />
        创建新小说
      </Title>

      <Steps current={currentStep} style={{ marginBottom: 24 }}>
        {steps.map(step => (
          <Steps.Step key={step.title} title={step.title} icon={step.icon} />
        ))}
      </Steps>

      {steps[currentStep]?.content}

      <Space style={{ marginTop: 16 }}>
        {currentStep > 0 && (
          <Button onClick={() => setCurrentStep(currentStep - 1)}>
            上一步
          </Button>
        )}
        {currentStep < steps.length - 1 && (
          <Button
            type="primary"
            onClick={() => setCurrentStep(currentStep + 1)}
            disabled={currentStep === 0 && !brief.user_brief}
          >
            下一步
          </Button>
        )}
      </Space>
    </div>
  )
}

export default NovelCreationWizardPage

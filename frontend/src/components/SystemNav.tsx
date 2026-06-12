import { useNavigate, useLocation } from 'react-router-dom'
import { Button, Space } from 'antd'
import { HomeOutlined } from '@ant-design/icons'
import ThemeSwitcher from '../themes/ThemeSwitcher'

interface SystemNavProps {
  /** Highlight the current page */
  current?: 'dashboard' | 'settings' | 'external-agent'
}

/**
 * Shared navigation bar for system-level pages:
 * Dashboard (作品管理). Settings and External Agent / MCP now live in the desktop GUI.
 */
function SystemNav({ current }: SystemNavProps) {
  const navigate = useNavigate()
  const location = useLocation()

  // Auto-detect current page if not specified
  const active = current || (() => {
    if (location.pathname === '/dashboard' || location.pathname === '/') return 'dashboard'
    return ''
  })()

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 20,
        paddingBottom: 14,
        borderBottom: '1px solid var(--ant-color-border-secondary)',
      }}
    >
      <Space size={8}>
        <Button
          type={active === 'dashboard' ? 'primary' : 'default'}
          icon={<HomeOutlined />}
          onClick={() => navigate('/dashboard')}
          style={{ borderRadius: 6 }}
        >
          作品管理
        </Button>
      </Space>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span
          style={{
            width: 1,
            height: 20,
            background: 'var(--ant-color-border-secondary)',
            display: 'inline-block',
          }}
        />
        <ThemeSwitcher />
      </div>
    </div>
  )
}

export default SystemNav

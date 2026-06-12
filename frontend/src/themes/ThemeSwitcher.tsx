import { Button, Dropdown, Tooltip } from 'antd'
import { BgColorsOutlined } from '@ant-design/icons'
import { useTheme } from './ThemeContext'

interface ThemeSwitcherProps {
  /** Show only the icon, no text — for collapsed sidebars */
  iconOnly?: boolean
}

function ThemeSwitcher({ iconOnly }: ThemeSwitcherProps) {
  const { currentTheme, setTheme, themes } = useTheme()

  const button = (
    <Button
      type="text"
      size="small"
      icon={<BgColorsOutlined />}
      style={{ opacity: 0.75, transition: 'opacity 0.2s ease' }}
    >
      {iconOnly ? null : `${currentTheme.icon} ${currentTheme.name}`}
    </Button>
  )

  return (
    <Tooltip title={iconOnly ? `${currentTheme.icon} ${currentTheme.name}` : undefined} placement={iconOnly ? 'right' : undefined}>
      <Dropdown
        menu={{
          items: themes.map((t) => ({
            key: t.key,
            label: (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 140, padding: '2px 0' }}>
                <div
                  style={{
                    width: 20,
                    height: 20,
                    borderRadius: '50%',
                    background: `linear-gradient(135deg, ${t.accent} 0%, ${t.accent}88 100%)`,
                    border: '2px solid rgba(0,0,0,0.06)',
                    flexShrink: 0,
                    boxShadow: `0 1px 3px ${t.accent}33`,
                  }}
                />
                <div>
                  <div style={{ fontWeight: t.key === currentTheme.key ? 700 : 400, fontSize: 13.5 }}>
                    {t.icon} {t.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ant-color-text-tertiary)', lineHeight: 1.3 }}>
                    {t.description}
                  </div>
                </div>
              </div>
            ),
          })),
          selectedKeys: [currentTheme.key],
          onClick: ({ key }) => setTheme(key),
          style: { minWidth: 180 },
        }}
        trigger={['click']}
        placement="bottomRight"
      >
        {button}
      </Dropdown>
    </Tooltip>
  )
}

export default ThemeSwitcher

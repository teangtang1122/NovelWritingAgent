import type { ThemeConfig } from 'antd'

export interface ThemeDefinition {
  key: string
  name: string
  description: string
  /** Icon emoji for the theme switcher */
  icon: string
  config: ThemeConfig
  /** CSS accent color for decorative use (borders, gradients) */
  accent: string
  /** Subtle background pattern opacity */
  grainOpacity: number
}

const FONT_BODY = "'LXGW WenKai', 'Noto Serif SC', 'PingFang SC', 'Microsoft YaHei', sans-serif"
const FONT_DISPLAY = "'Noto Serif SC', 'LXGW WenKai', 'PingFang SC', serif"

/** 文房 — 温润、沉静、文学感 */
const wenfang: ThemeDefinition = {
  key: 'wenfang',
  name: '文房',
  description: '温润沉静，文学气息',
  icon: '📜',
  accent: '#7c5e2a',
  grainOpacity: 0.018,
  config: {
    token: {
      colorPrimary: '#7c5e2a',
      colorSuccess: '#5a8a3c',
      colorWarning: '#c48816',
      colorError: '#b84233',
      colorInfo: '#7c5e2a',
      colorBgLayout: '#f6f2ea',
      colorBgContainer: '#fffcf5',
      colorBgElevated: '#fffcf5',
      colorText: '#2c2417',
      colorTextSecondary: '#7a6e5b',
      colorTextTertiary: '#a89c88',
      colorTextQuaternary: '#d0c8b8',
      colorBorder: '#e4ddd0',
      colorBorderSecondary: '#ece7dc',
      borderRadius: 6,
      borderRadiusLG: 8,
      boxShadow: '0 1px 3px rgba(44, 36, 23, 0.06), 0 1px 2px rgba(44, 36, 23, 0.04)',
      boxShadowSecondary: '0 4px 16px rgba(44, 36, 23, 0.08), 0 2px 6px rgba(44, 36, 23, 0.04)',
      fontFamily: FONT_BODY,
    },
    components: {
      Layout: { bodyBg: '#f6f2ea', siderBg: '#fffcf5', headerBg: '#f5f1e9' },
      Menu: {
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
        itemSelectedBg: 'rgba(124, 94, 42, 0.08)',
        itemSelectedColor: '#7c5e2a',
        itemHoverBg: 'rgba(124, 94, 42, 0.04)',
        itemActiveBg: 'rgba(124, 94, 42, 0.12)',
        itemBorderRadius: 6,
        itemMarginInline: 8,
        itemPaddingInline: 12,
      },
      Card: { colorBgContainer: '#fffcf5', boxShadow: '0 1px 3px rgba(44, 36, 23, 0.06)' },
      Table: { colorBgContainer: '#fffcf5', headerBg: '#f5f1e9', rowHoverBg: '#faf6ee' },
      Input: { colorBgContainer: '#fffcf5', activeShadow: '0 0 0 2px rgba(124, 94, 42, 0.12)' },
      Select: { colorBgContainer: '#fffcf5' },
      Modal: { contentBg: '#fffcf5', titleFontSize: 17 },
      Tabs: { inkBarColor: '#7c5e2a', itemSelectedColor: '#7c5e2a', itemHoverColor: '#9a7d3e' },
      Tag: { defaultBg: '#faf6ee', defaultColor: '#7c5e2a' },
      Button: { primaryShadow: '0 2px 4px rgba(124, 94, 42, 0.2)' },
    },
  },
}

/** 墨白 — 清爽、高对比度、书卷气 */
const mobai: ThemeDefinition = {
  key: 'mobai',
  name: '墨白',
  description: '清爽素雅，黑白分明',
  icon: '🖋️',
  accent: '#2a2a2a',
  grainOpacity: 0.012,
  config: {
    token: {
      colorPrimary: '#2a2a2a',
      colorSuccess: '#52c41a',
      colorWarning: '#faad14',
      colorError: '#f5222d',
      colorInfo: '#2a2a2a',
      colorBgLayout: '#f7f7f7',
      colorBgContainer: '#ffffff',
      colorBgElevated: '#ffffff',
      colorText: '#111111',
      colorTextSecondary: '#555555',
      colorTextTertiary: '#8c8c8c',
      colorTextQuaternary: '#bfbfbf',
      colorBorder: '#d9d9d9',
      colorBorderSecondary: '#f0f0f0',
      borderRadius: 4,
      borderRadiusLG: 6,
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.03)',
      boxShadowSecondary: '0 4px 16px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0, 0, 0, 0.03)',
      fontFamily: FONT_BODY,
    },
    components: {
      Layout: { bodyBg: '#f7f7f7', siderBg: '#ffffff', headerBg: '#fafafa' },
      Menu: {
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
        itemSelectedBg: '#f0f0f0',
        itemSelectedColor: '#111111',
        itemHoverBg: '#f5f5f5',
        itemActiveBg: '#e8e8e8',
        itemBorderRadius: 4,
        itemMarginInline: 8,
        itemPaddingInline: 12,
      },
      Card: { colorBgContainer: '#ffffff', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)' },
      Table: { colorBgContainer: '#ffffff', headerBg: '#fafafa', rowHoverBg: '#f5f5f5' },
      Input: { colorBgContainer: '#ffffff', activeShadow: '0 0 0 2px rgba(42, 42, 42, 0.1)' },
      Select: { colorBgContainer: '#ffffff' },
      Modal: { contentBg: '#ffffff', titleFontSize: 17 },
      Tabs: { inkBarColor: '#111111', itemSelectedColor: '#111111', itemHoverColor: '#2a2a2a' },
      Tag: { defaultBg: '#f5f5f5', defaultColor: '#2a2a2a' },
      Button: { primaryShadow: '0 2px 4px rgba(0, 0, 0, 0.15)' },
    },
  },
}

/** 青竹 — 清新、自然、生机 */
const qingzhu: ThemeDefinition = {
  key: 'qingzhu',
  name: '青竹',
  description: '清新自然，竹韵悠然',
  icon: '🎋',
  accent: '#2d6b4e',
  grainOpacity: 0.014,
  config: {
    token: {
      colorPrimary: '#2d6b4e',
      colorSuccess: '#52c41a',
      colorWarning: '#d4a843',
      colorError: '#c44a3f',
      colorInfo: '#2d6b4e',
      colorBgLayout: '#f0f6f2',
      colorBgContainer: '#f8fbf9',
      colorBgElevated: '#f8fbf9',
      colorText: '#1a2e23',
      colorTextSecondary: '#5a7d6a',
      colorTextTertiary: '#8aa496',
      colorTextQuaternary: '#b8cfc3',
      colorBorder: '#c0d8ca',
      colorBorderSecondary: '#d8ece2',
      borderRadius: 8,
      borderRadiusLG: 10,
      boxShadow: '0 1px 3px rgba(45, 107, 78, 0.06), 0 1px 2px rgba(45, 107, 78, 0.04)',
      boxShadowSecondary: '0 4px 16px rgba(45, 107, 78, 0.08), 0 2px 6px rgba(45, 107, 78, 0.04)',
      fontFamily: FONT_BODY,
    },
    components: {
      Layout: { bodyBg: '#f0f6f2', siderBg: '#f8fbf9', headerBg: '#eaf3ed' },
      Menu: {
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
        itemSelectedBg: 'rgba(45, 107, 78, 0.08)',
        itemSelectedColor: '#2d6b4e',
        itemHoverBg: 'rgba(45, 107, 78, 0.04)',
        itemActiveBg: 'rgba(45, 107, 78, 0.12)',
        itemBorderRadius: 8,
        itemMarginInline: 8,
        itemPaddingInline: 12,
      },
      Card: { colorBgContainer: '#f8fbf9', boxShadow: '0 1px 3px rgba(45, 107, 78, 0.06)' },
      Table: { colorBgContainer: '#f8fbf9', headerBg: '#eaf3ed', rowHoverBg: '#e8f2ec' },
      Input: { colorBgContainer: '#f8fbf9', activeShadow: '0 0 0 2px rgba(45, 107, 78, 0.12)' },
      Select: { colorBgContainer: '#f8fbf9' },
      Modal: { contentBg: '#f8fbf9', titleFontSize: 17 },
      Tabs: { inkBarColor: '#2d6b4e', itemSelectedColor: '#2d6b4e', itemHoverColor: '#4a9e7a' },
      Tag: { defaultBg: '#e8f2ec', defaultColor: '#2d6b4e' },
      Button: { primaryShadow: '0 2px 4px rgba(45, 107, 78, 0.2)' },
    },
  },
}

/** 夜读 — 暗色、护眼、沉浸 */
const yedu: ThemeDefinition = {
  key: 'yedu',
  name: '夜读',
  description: '暗色沉浸，深夜护眼',
  icon: '🌙',
  accent: '#c9a04e',
  grainOpacity: 0.025,
  config: {
    algorithm: undefined, // Will be set to darkAlgorithm at runtime
    token: {
      colorPrimary: '#c9a04e',
      colorSuccess: '#6abf4b',
      colorWarning: '#e8b84d',
      colorError: '#d4534d',
      colorInfo: '#c9a04e',
      colorBgLayout: '#161310',
      colorBgContainer: '#1e1b17',
      colorBgElevated: '#252119',
      colorText: '#e5dcc8',
      colorTextSecondary: '#a09278',
      colorTextTertiary: '#706450',
      colorTextQuaternary: '#4a4236',
      colorBorder: '#362f25',
      colorBorderSecondary: '#2a2419',
      borderRadius: 6,
      borderRadiusLG: 8,
      boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2), 0 1px 2px rgba(0, 0, 0, 0.12)',
      boxShadowSecondary: '0 4px 16px rgba(0, 0, 0, 0.25), 0 2px 6px rgba(0, 0, 0, 0.15)',
      fontFamily: FONT_BODY,
    },
    components: {
      Layout: { bodyBg: '#161310', siderBg: '#1e1b17', headerBg: '#1a1714' },
      Menu: {
        itemBg: 'transparent',
        subMenuItemBg: 'transparent',
        itemSelectedBg: 'rgba(201, 160, 78, 0.12)',
        itemSelectedColor: '#c9a04e',
        itemHoverBg: 'rgba(201, 160, 78, 0.06)',
        itemActiveBg: 'rgba(201, 160, 78, 0.18)',
        itemBorderRadius: 6,
        itemMarginInline: 8,
        itemPaddingInline: 12,
      },
      Card: { colorBgContainer: '#1e1b17', boxShadow: '0 1px 3px rgba(0, 0, 0, 0.2)' },
      Table: { colorBgContainer: '#1e1b17', headerBg: '#252119', rowHoverBg: '#2a2419' },
      Input: { colorBgContainer: '#252119', activeShadow: '0 0 0 2px rgba(201, 160, 78, 0.15)' },
      Select: { colorBgContainer: '#252119' },
      Modal: { contentBg: '#1e1b17', titleFontSize: 17 },
      Tabs: { inkBarColor: '#c9a04e', itemSelectedColor: '#c9a04e', itemHoverColor: '#b8922e' },
      Tag: { defaultBg: '#2a2419', defaultColor: '#c9a04e' },
      Button: { primaryShadow: '0 2px 4px rgba(201, 160, 78, 0.15)' },
    },
  },
}

export const THEMES: ThemeDefinition[] = [wenfang, mobai, qingzhu, yedu]

export const DEFAULT_THEME_KEY = 'wenfang'

export { FONT_BODY, FONT_DISPLAY }

export function getThemeByKey(key: string): ThemeDefinition {
  return THEMES.find((t) => t.key === key) || wenfang
}

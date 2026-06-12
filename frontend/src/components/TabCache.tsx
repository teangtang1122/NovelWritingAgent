import { useRef, type ReactNode } from 'react'

interface TabCacheProps {
  /** Currently active tab key */
  activeKey: string
  /** Map of tab key → render function */
  tabs: Record<string, () => ReactNode>
}

/**
 * Keeps previously-rendered tab content in memory so switching back
 * is instant — no re-mount, no re-fetch, no animation jank.
 *
 * Inactive tabs are hidden with `display: none` instead of unmounting.
 */
export default function TabCache({ activeKey, tabs }: TabCacheProps) {
  const cacheRef = useRef<Record<string, ReactNode>>({})

  // Render the active tab into cache if not already present
  if (!cacheRef.current[activeKey] && tabs[activeKey]) {
    cacheRef.current[activeKey] = tabs[activeKey]()
  }

  return (
    <>
      {Object.entries(cacheRef.current).map(([key, node]) => (
        <div
          key={key}
          style={{ display: key === activeKey ? 'contents' : 'none' }}
        >
          {node}
        </div>
      ))}
    </>
  )
}

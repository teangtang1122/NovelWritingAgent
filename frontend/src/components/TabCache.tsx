import { useRef, useState, useEffect, type ReactNode } from 'react'

interface TabCacheProps {
  /** Currently active tab key */
  activeKey: string
  /** Map of tab key → render function */
  tabs: Record<string, () => ReactNode>
}

/**
 * Keeps previously-rendered tab content in memory so switching back
 * is instant — no re-mount, no re-fetch.
 *
 * Inactive tabs are hidden with `display: none`.
 * Active tab gets a brief fade-in animation for switch feedback.
 */
export default function TabCache({ activeKey, tabs }: TabCacheProps) {
  const cacheRef = useRef<Record<string, ReactNode>>({})
  const [fadeInKey, setFadeInKey] = useState<string | null>(null)

  // Render the active tab into cache if not already present
  if (!cacheRef.current[activeKey] && tabs[activeKey]) {
    cacheRef.current[activeKey] = tabs[activeKey]()
  }

  // Trigger fade-in animation on tab switch
  useEffect(() => {
    setFadeInKey(activeKey)
    const timer = setTimeout(() => setFadeInKey(null), 200)
    return () => clearTimeout(timer)
  }, [activeKey])

  return (
    <>
      {Object.entries(cacheRef.current).map(([key, node]) => (
        <div
          key={key}
          className={key === activeKey && key === fadeInKey ? 'tab-cache-fade-in' : undefined}
          style={{ display: key === activeKey ? 'contents' : 'none' }}
        >
          {node}
        </div>
      ))}
    </>
  )
}

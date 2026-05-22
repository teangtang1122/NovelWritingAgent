/**
 * Test setup file for vitest.
 * Provides global mocks required by antd and other dependencies.
 * NOTE: vi.mock calls belong in individual test files, not here.
 */

import '@testing-library/jest-dom/vitest'

// Mock window.matchMedia (required by antd)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

// Mock getComputedStyle (required by antd components)
const originalGetComputedStyle = window.getComputedStyle
window.getComputedStyle = (element: Element, pseudoElt?: string | null) => {
  const style = originalGetComputedStyle(element, pseudoElt)
  return style
}

// Suppress antd deprecation warnings in tests
const originalWarn = console.warn
console.warn = (...args: unknown[]) => {
  const msg = String(args[0])
  if (msg.includes('findDOMNode') || msg.includes('defaultProps')) {
    return
  }
  originalWarn(...args)
}

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  root = null
  rootMargin = ''
  thresholds = []
  takeRecords = () => []
}
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: MockIntersectionObserver,
})

// Mock scrollTo
window.scrollTo = () => {}

// Mock ResizeObserver
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: MockResizeObserver,
})

/**
 * Tests for useDebounce hook.
 *
 * Uses vi.useFakeTimers() to control setTimeout precisely so tests are
 * deterministic and run instantly — no real delays.
 *
 * Each test manages timer state explicitly: fake timers are installed in
 * beforeEach and real timers are restored in afterEach to avoid bleed-through
 * that can destabilize other test files.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '../useDebounce'

// ─── Timer setup / teardown ───────────────────────────────────────────────────

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

// ─── Initial value ────────────────────────────────────────────────────────────

describe('useDebounce — initial value', () => {
  it('returns the initial value synchronously on first render', () => {
    /**Should expose the starting value immediately before any delay elapses */
    const { result } = renderHook(() => useDebounce('hello', 300))
    expect(result.current).toBe('hello')
  })

  it('returns numeric initial value correctly', () => {
    /**Should work with any generic type, not just strings */
    const { result } = renderHook(() => useDebounce(42, 500))
    expect(result.current).toBe(42)
  })

  it('returns object initial value correctly', () => {
    /**Should work with object types without mutation */
    const initial = { query: 'test' }
    const { result } = renderHook(() => useDebounce(initial, 200))
    expect(result.current).toBe(initial)
  })
})

// ─── Debounce window: value must NOT update before delay ─────────────────────

describe('useDebounce — value stays unchanged within the delay window', () => {
  it('does not update if timer has not elapsed yet', () => {
    /**Should suppress intermediate values to prevent excessive API calls */
    const { result, rerender } = renderHook(
      ({ value, delay }: { value: string; delay: number }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 500 } },
    )

    rerender({ value: 'changed', delay: 500 })

    // Advance time to just before the delay — should still see old value
    act(() => {
      vi.advanceTimersByTime(499)
    })

    expect(result.current).toBe('initial')
  })

  it('does not update immediately when value changes', () => {
    /**Value change must be buffered, not applied synchronously */
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebounce(value, 300),
      { initialProps: { value: 'start' } },
    )

    rerender({ value: 'end' })

    // No timer advancement — value must still be the original
    expect(result.current).toBe('start')
  })
})

// ─── Debounce window: value MUST update after delay ──────────────────────────

describe('useDebounce — value updates after the delay elapses', () => {
  it('updates to the new value after exactly the delay ms', () => {
    /**Should emit the latest value once the debounce timer fires */
    const { result, rerender } = renderHook(
      ({ value, delay }: { value: string; delay: number }) => useDebounce(value, delay),
      { initialProps: { value: 'initial', delay: 300 } },
    )

    rerender({ value: 'updated', delay: 300 })

    act(() => {
      vi.advanceTimersByTime(300)
    })

    expect(result.current).toBe('updated')
  })

  it('updates after delay for numeric values', () => {
    /**Should flush numeric debounced updates correctly */
    const { result, rerender } = renderHook(
      ({ value }: { value: number }) => useDebounce(value, 200),
      { initialProps: { value: 0 } },
    )

    rerender({ value: 99 })

    act(() => {
      vi.advanceTimersByTime(200)
    })

    expect(result.current).toBe(99)
  })

  it('updates after delay for boolean values', () => {
    /**Should handle boolean types (e.g. feature flags) without coercion */
    const { result, rerender } = renderHook(
      ({ value }: { value: boolean }) => useDebounce(value, 150),
      { initialProps: { value: false } },
    )

    rerender({ value: true })

    act(() => {
      vi.advanceTimersByTime(150)
    })

    expect(result.current).toBe(true)
  })
})

// ─── Rapid changes cancel previous timers ────────────────────────────────────

describe('useDebounce — rapid changes cancel prior timers', () => {
  it('only emits the final value when multiple changes happen within the window', () => {
    /**
     * Should cancel any pending timer when a new value arrives, preventing
     * stale intermediate values from reaching the debounced output — this is
     * the core "search-as-you-type" use case.
     */
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebounce(value, 300),
      { initialProps: { value: '' } },
    )

    rerender({ value: 'a' })
    act(() => { vi.advanceTimersByTime(100) })

    rerender({ value: 'ab' })
    act(() => { vi.advanceTimersByTime(100) })

    rerender({ value: 'abc' })
    act(() => { vi.advanceTimersByTime(100) })

    // Total: 300ms elapsed since the last value, but the timer was reset each
    // time. The debounced output should still be the initial '' because 300ms
    // haven't elapsed since the LAST change ('abc' at t=200ms; now at t=300ms).
    expect(result.current).toBe('')

    // Now let the final debounce timer fire (300ms after 'abc')
    act(() => { vi.advanceTimersByTime(300) })

    expect(result.current).toBe('abc')
  })

  it('intermediate values are dropped when changes arrive faster than the delay', () => {
    /**Should never emit a stale intermediate value — only the last one counts */
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebounce(value, 500),
      { initialProps: { value: 'start' } },
    )

    // Three rapid updates — none complete their individual timers
    rerender({ value: 'first-update' })
    act(() => { vi.advanceTimersByTime(100) })

    rerender({ value: 'second-update' })
    act(() => { vi.advanceTimersByTime(100) })

    rerender({ value: 'final-value' })
    // Still within the debounce window — no update yet
    expect(result.current).toBe('start')

    // Let the debounce settle for the last value
    act(() => { vi.advanceTimersByTime(500) })

    expect(result.current).toBe('final-value')
  })

  it('emits the first value immediately after delay when only one change was made', () => {
    /**Control case: single change → timer fires once with that value */
    const { result, rerender } = renderHook(
      ({ value }: { value: string }) => useDebounce(value, 250),
      { initialProps: { value: 'original' } },
    )

    rerender({ value: 'one-change' })

    act(() => { vi.advanceTimersByTime(250) })

    expect(result.current).toBe('one-change')
  })
})

// ─── Delay parameter changes ──────────────────────────────────────────────────

describe('useDebounce — delay parameter changes', () => {
  it('uses the new delay if the delay parameter itself changes', () => {
    /**Should adapt to a changed delay — e.g. slow network conditions */
    const { result, rerender } = renderHook(
      ({ value, delay }: { value: string; delay: number }) => useDebounce(value, delay),
      { initialProps: { value: 'hello', delay: 300 } },
    )

    // Change both value and delay simultaneously
    rerender({ value: 'world', delay: 600 })

    // Only 300ms in — old delay would have fired, but new delay is 600ms
    act(() => { vi.advanceTimersByTime(300) })
    expect(result.current).toBe('hello')

    // Complete the new delay
    act(() => { vi.advanceTimersByTime(300) })
    expect(result.current).toBe('world')
  })
})

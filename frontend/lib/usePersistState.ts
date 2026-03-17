"use client";

import { useState, useEffect, useCallback } from "react";

const PREFIX = "ig_persist_";

/**
 * Persists state to sessionStorage and restores on mount.
 * Use for form drafts and in-progress results to survive accidental reloads.
 */
export function usePersistState<T>(
  key: string,
  initialState: T,
  options?: { serialize?: (v: T) => string; deserialize?: (s: string) => T }
): [T, (value: T | ((prev: T) => T)) => void] {
  const storageKey = `${PREFIX}${key}`;
  const serialize = options?.serialize ?? JSON.stringify;
  const deserialize = options?.deserialize ?? JSON.parse;

  const [state, setState] = useState<T>(() => {
    if (typeof window === "undefined") return initialState;
    try {
      const stored = sessionStorage.getItem(storageKey);
      if (stored) return deserialize(stored) as T;
    } catch {
      // Invalid JSON or missing, use initial
    }
    return initialState;
  });

  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey, serialize(state));
    } catch {
      // quota exceeded or other error
    }
  }, [storageKey, state, serialize]);

  const setValue = useCallback(
    (value: T | ((prev: T) => T)) => {
      setState((prev) => {
        const next = typeof value === "function" ? (value as (p: T) => T)(prev) : value;
        return next;
      });
    },
    []
  );

  return [state, setValue];
}

/** Clear persisted state for a key (e.g. when user explicitly "starts fresh") */
export function clearPersistedState(key: string) {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(`${PREFIX}${key}`);
}

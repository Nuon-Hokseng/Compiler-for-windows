"use client";

import { useEffect } from "react";

/**
 * Shows the browser's native "Leave site?" dialog when the user tries to
 * reload, close the tab, or navigate away while `enabled` is true.
 */
export function useBeforeUnload(enabled: boolean) {
  useEffect(() => {
    if (!enabled) return;

    function handleBeforeUnload(e: BeforeUnloadEvent) {
      e.preventDefault();
      // Modern browsers show a generic message; setting returnValue is required for legacy support
      e.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [enabled]);
}

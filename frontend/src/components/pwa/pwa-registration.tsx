"use client";

import { useEffect } from "react";

/** Registers the small, project-owned service worker after hydration. */
export function PwaRegistration() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Offline support is optional; keep the application available if registration fails.
      });
    }
  }, []);

  return null;
}

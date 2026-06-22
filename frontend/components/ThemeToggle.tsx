"use client";

import { useEffect, useState } from "react";

type Theme = "day" | "night";

const storageKey = "aud-generator-theme";

function getInitialTheme(): Theme {
  if (typeof window === "undefined") {
    return "day";
  }

  const storedTheme = window.localStorage.getItem(storageKey);
  if (storedTheme === "day" || storedTheme === "night") {
    return storedTheme;
  }

  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("day");
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const initialTheme = getInitialTheme();
    document.body.classList.toggle("theme-dark", initialTheme === "night");
    setTheme(initialTheme);
    setIsReady(true);
  }, []);

  useEffect(() => {
    if (!isReady) {
      return;
    }

    document.body.classList.toggle("theme-dark", theme === "night");
    window.localStorage.setItem(storageKey, theme);
  }, [isReady, theme]);

  const nextTheme = theme === "day" ? "night" : "day";

  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${nextTheme} mode`}
      aria-pressed={theme === "night"}
      onClick={() => setTheme(nextTheme)}
    >
      <span className="theme-toggle-thumb" aria-hidden="true" />
      <span className="theme-toggle-icon theme-toggle-sun" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <circle cx="12" cy="12" r="4.2" />
          <path d="M12 2.8v2.4M12 18.8v2.4M4.18 4.18l1.7 1.7M18.12 18.12l1.7 1.7M2.8 12h2.4M18.8 12h2.4M4.18 19.82l1.7-1.7M18.12 5.88l1.7-1.7" />
        </svg>
      </span>
      <span className="theme-toggle-icon theme-toggle-moon" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          <path d="M20.2 14.7A7.9 7.9 0 0 1 9.3 3.8a8.9 8.9 0 1 0 10.9 10.9Z" />
        </svg>
      </span>
      <span className="sr-only">{theme === "day" ? "Day mode" : "Night mode"}</span>
    </button>
  );
}

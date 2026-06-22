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
    document.documentElement.dataset.theme = initialTheme;
    setTheme(initialTheme);
    setIsReady(true);
  }, []);

  useEffect(() => {
    if (!isReady) {
      return;
    }

    document.documentElement.dataset.theme = theme;
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
      <span className="theme-toggle-icon" aria-hidden="true">
        {theme === "day" ? "D" : "N"}
      </span>
      <span>{theme === "day" ? "Day" : "Night"}</span>
    </button>
  );
}

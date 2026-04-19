export type Theme = "light" | "dark";

const STORAGE_KEY = "werewolf.theme";
const DATA_ATTR = "data-theme";

function readSystemPreference(): Theme {
  if (typeof window === "undefined") {
    return "light";
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)")?.matches
    ? "dark"
    : "light";
}

function readStoredTheme(): Theme | null {
  if (typeof window === "undefined") {
    return null;
  }
  const stored = window.localStorage?.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : null;
}

export function resolveInitialTheme(): Theme {
  return readStoredTheme() ?? readSystemPreference();
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.setAttribute(DATA_ATTR, theme);
}

export function persistTheme(theme: Theme): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage?.setItem(STORAGE_KEY, theme);
}

export function toggleTheme(theme: Theme): Theme {
  return theme === "light" ? "dark" : "light";
}

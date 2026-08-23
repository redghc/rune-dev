// Theme controller — single source of truth for ``light`` / ``dark`` /
// ``auto``. Persists the user's choice in localStorage, writes the
// matching ``sl-theme-*`` class onto ``<html>`` (Shoelace picks the
// palette from that), and broadcasts a ``rune-theme-change`` event so
// UI bits (toggle component, status pill, etc.) can re-render.

export type RuneTheme = "auto" | "light" | "dark";

const STORAGE_KEY = "rune-theme";
const VALID: readonly RuneTheme[] = ["auto", "light", "dark"];

function readStored(): RuneTheme {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && (VALID as readonly string[]).includes(raw)) {
      return raw as RuneTheme;
    }
  } catch {
    /* localStorage may be unavailable (private mode, sandboxed iframe) */
  }
  return "auto";
}

function applyToDocument(theme: RuneTheme): void {
  const html = document.documentElement;
  html.classList.remove("sl-theme-light", "sl-theme-dark");
  if (theme === "light") html.classList.add("sl-theme-light");
  else if (theme === "dark") html.classList.add("sl-theme-dark");
  // ``auto`` = no class — the CSS ``@media (prefers-color-scheme: dark)``
  // in shared.ts takes over.
}

let current: RuneTheme = "auto";
const listeners = new Set<(t: RuneTheme) => void>();

export function getTheme(): RuneTheme {
  return current;
}

export function setTheme(theme: RuneTheme): void {
  if (!VALID.includes(theme)) return;
  current = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
  applyToDocument(theme);
  for (const fn of listeners) fn(theme);
}

export function onThemeChange(fn: (t: RuneTheme) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Read the stored preference and apply it to the document. Called
 *  once at app bootstrap so the rest of the UI can read ``getTheme``
 *  synchronously. */
export function initTheme(): RuneTheme {
  current = readStored();
  applyToDocument(current);
  return current;
}

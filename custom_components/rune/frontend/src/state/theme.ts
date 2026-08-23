// Theme controller — single source of truth for ``light`` / ``dark`` /
// ``auto``. Persists the user's choice in localStorage, writes the
// matching ``sl-theme-*`` class onto ``<html>`` (Shoelace picks the
// palette from that), and broadcasts a change event so UI bits
// (toggle component, status pill, etc.) can re-render.

import { createPref } from "./pref.js";

export type RuneTheme = "auto" | "light" | "dark";

const VALID: readonly RuneTheme[] = ["auto", "light", "dark"];

const applyToDocument = (theme: RuneTheme): void => {
  const html = document.documentElement;
  html.classList.remove("sl-theme-light", "sl-theme-dark");
  if (theme === "light") html.classList.add("sl-theme-light");
  else if (theme === "dark") html.classList.add("sl-theme-dark");
  // ``auto`` = no class — the CSS ``@media (prefers-color-scheme: dark)``
  // in shared.ts takes over.
};

const pref = createPref<RuneTheme>({
  key: "rune-theme",
  initial: "auto",
  valid: VALID,
});

export const getTheme = pref.get;
export const setTheme = (theme: RuneTheme): void => {
  pref.set(theme);
  applyToDocument(theme);
};
export const onThemeChange = pref.subscribe;

/** Read the stored preference and apply it to the document. Called
 *  once at app bootstrap so the rest of the UI can read ``getTheme``
 *  synchronously. */
export const initTheme = (): RuneTheme => {
  const theme = pref.init();
  applyToDocument(theme);
  return theme;
};

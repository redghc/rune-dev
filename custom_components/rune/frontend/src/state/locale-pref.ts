// Locale preference — single source of truth for the user's chosen
// language. Persists in localStorage so the override survives HA
// reloads. When unset (or set to "auto"), the i18n bootstrap falls
// back to whatever Home Assistant reports via the postMessage
// ``rune-init`` handshake.
//
// We intentionally keep this *separate* from ``store.locale``: the
// store holds the HA-reported value (and may get refreshed), while
// the preference is the sticky user choice. The i18n module consults
// the preference first.

import { createPref } from "./pref.js";

export type LocalePref = "auto" | "en" | "es";

const VALID: readonly LocalePref[] = ["auto", "en", "es"];

const pref = createPref<LocalePref>({
  key: "rune-locale",
  initial: "auto",
  valid: VALID,
});

export const getLocalePref = pref.get;
export const setLocalePref = pref.set;
export const onLocalePrefChange = pref.subscribe;

/** Read the stored preference. Called once at app bootstrap so the
 *  rest of the UI can read ``getLocalePref`` synchronously. */
export const initLocalePref = pref.init;

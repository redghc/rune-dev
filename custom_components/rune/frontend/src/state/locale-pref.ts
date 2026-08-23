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

export type LocalePref = "auto" | "en" | "es";

const STORAGE_KEY = "rune-locale";
const VALID: readonly LocalePref[] = ["auto", "en", "es"];

export const SUPPORTED_LOCALES: readonly Exclude<LocalePref, "auto">[] = ["en", "es"];

function readStored(): LocalePref {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && (VALID as readonly string[]).includes(raw)) {
      return raw as LocalePref;
    }
  } catch {
    /* localStorage may be unavailable (private mode, sandboxed iframe) */
  }
  return "auto";
}

let current: LocalePref = "auto";
const listeners = new Set<(p: LocalePref) => void>();

export function getLocalePref(): LocalePref {
  return current;
}

export function setLocalePref(pref: LocalePref): void {
  if (!VALID.includes(pref)) return;
  if (pref === current) return;
  current = pref;
  try {
    if (pref === "auto") {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, pref);
    }
  } catch {
    /* ignore */
  }
  for (const fn of listeners) fn(pref);
}

export function onLocalePrefChange(fn: (p: LocalePref) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Read the stored preference. Called once at app bootstrap so the
 *  rest of the UI can read ``getLocalePref`` synchronously. */
export function initLocalePref(): LocalePref {
  current = readStored();
  return current;
}

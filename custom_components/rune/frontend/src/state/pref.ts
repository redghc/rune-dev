// Generic localStorage-backed preference store.
//
// Two consumers (theme.ts, locale-pref.ts) used to carry near-identical
// machinery: a STORAGE_KEY, a VALID set, a read/write helper, a listener
// Set, and a get/set/on*/init surface. This factory collapses all of it
// into one place so the per-domain modules just declare the value type
// and the valid set.
//
// SSR-safe: every localStorage call is wrapped so private mode /
// sandboxed iframes that throw on access don't break the app.

export interface PrefController<T extends string> {
  get(): T;
  set(next: T): void;
  subscribe(fn: (v: T) => void): () => void;
  init(): T;
}

export interface PrefOptions<T extends string> {
  key: string;
  initial: T;
  valid: readonly T[];
}

export function createPref<T extends string>(opts: PrefOptions<T>): PrefController<T> {
  const { key, initial, valid } = opts;
  const validAsStrings = valid as readonly string[];

  const read = (): T => {
    try {
      const raw = localStorage.getItem(key);
      if (raw && validAsStrings.includes(raw)) {
        return raw as T;
      }
    } catch {
      /* localStorage may be unavailable */
    }
    return initial;
  };

  const write = (value: T): void => {
    try {
      if (value === initial) {
        localStorage.removeItem(key);
      } else {
        localStorage.setItem(key, value);
      }
    } catch {
      /* ignore */
    }
  };

  let current: T = initial;
  const listeners = new Set<(v: T) => void>();

  const notify = (): void => {
    for (const fn of listeners) fn(current);
  };

  return {
    get: () => current,
    set: (next) => {
      if (!validAsStrings.includes(next)) return;
      if (next === current) return;
      current = next;
      write(next);
      notify();
    },
    subscribe: (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    init: () => {
      current = read();
      return current;
    },
  };
}

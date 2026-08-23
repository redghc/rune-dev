// Display formatting helpers.
//
// Kept dependency-free so the file is safe to import from any layer
// (state, view, UI primitives) without dragging in Lit, Shoelace, or
// the i18n runtime.

/** English-style pluralization: ``pluralize(1, "signal") === "signal"``,
 *  ``pluralize(2, "signal") === "signals"``. Pass an explicit plural
 *  for irregular nouns (``pluralize(2, "child", "children")``). */
export const pluralize = (n: number, singular: string, plural?: string): string =>
  `${n} ${n === 1 ? singular : (plural ?? `${singular}s`)}`;

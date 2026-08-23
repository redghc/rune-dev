// Display formatting helpers.
//
// Kept dependency-free so the file is safe to import from any layer
// (state, view, UI primitives) without dragging in Lit, Shoelace, or
// the i18n runtime.

/** Drop empty strings from a tuple of candidates. Used to collapse the
 *  ``ir_*`` / ``rf_*`` form fields into a single ``transmitter_entity_ids``
 *  list without dragging in a ``.filter(...)[0]`` (oxlint flags that as
 *  a misread ``.filter(...)[0]``). */
export const nonEmpty = (...values: string[]): string[] => {
  const out: string[] = [];
  for (const v of values) if (v !== "") out.push(v);
  return out;
};

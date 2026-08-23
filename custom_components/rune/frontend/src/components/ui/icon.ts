// Tabler Icons — lightweight wrapper around @tabler/icons-webfont.
//
// The webfont package ships ``.ttf`` + ``.woff`` + ``.woff2`` + a CSS
// file referencing all three. We deliberately skip the bundled CSS
// (which forces Vite-singlefile to inline all three fonts as base64,
// bloating the bundle by ~5MB) and emit our own minimal CSS that only
// references the ``.woff2`` (~455KB → ~607KB base64). The browser
// ignores unsupported formats so we lose nothing visually.
//
// The styles are installed via a single shared ``CSSStyleSheet`` that
// is adopted into ``document.adoptedStyleSheets`` and into every
// shadow root created afterwards. Injecting a ``<style>`` tag into
// ``document.head`` would NOT work: the icons live inside Lit shadow
// roots, and CSS in the light DOM does not cross shadow boundaries.
//
// Usage:
//   import { tablerIcon } from "@/components/ui/icon.js";
//   html`<span class="icon">${tablerIcon("remote")}</span>`
//   html`<rune-icon name="remote"></rune-icon>`

import tablerWoff2 from "@tabler/icons-webfont/dist/fonts/tabler-icons.woff2?url";
// ``?raw`` returns the file as a string WITHOUT Vite rewriting any
// ``url(...)`` references — critical because the bundled CSS points
// at woff + ttf + woff2 and ``?inline`` would inline all three fonts.
import codepoints from "@tabler/icons-webfont/dist/tabler-icons.css?raw";

let iconSheet: CSSStyleSheet | null = null;

function buildIconSheet(): CSSStyleSheet {
  const raw = codepoints as unknown as string;

  // Strip the original @font-face block (which pulls in ttf+woff+woff2)
  // and the leading license comment. We re-emit a slim woff2-only
  // version below.
  const codepointCss = raw
    .replace(/@font-face\s*\{[^}]*\}/g, "")
    .replace(/^\/\*![\s\S]*?\*\/\s*/, "")
    .trim();

  const fontCss = `
@font-face {
  font-family: "tabler-icons";
  font-style: normal;
  font-weight: 400;
  font-display: block;
  src: url(${tablerWoff2}) format("woff2");
}
.ti {
  font-family: "tabler-icons" !important;
  speak: never;
  font-style: normal;
  font-weight: normal;
  font-variant: normal;
  text-transform: none;
  line-height: 1;
  letter-spacing: 0;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
${codepointCss}
`;
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(fontCss);
  return sheet;
}

function getIconSheet(): CSSStyleSheet {
  if (!iconSheet) iconSheet = buildIconSheet();
  return iconSheet;
}

function adoptInto(root: DocumentOrShadowRoot): void {
  const sheet = getIconSheet();
  const current = root.adoptedStyleSheets ?? [];
  if (!current.includes(sheet)) {
    root.adoptedStyleSheets = [...current, sheet];
  }
}

function inject(): void {
  if (typeof document === "undefined") return;
  adoptInto(document);
}

// Side-effect: inject immediately on module load so consumers never
// need to remember to call a setup fn.
inject();

// One-time patch: every new shadow root also gets the icon sheet. We
// can't iterate existing roots (they may not be created yet) and we
// don't want a per-component base class for the sake of one stylesheet.
// Patching ``attachShadow`` covers Lit, Shoelace, and any other custom
// element without opt-in.
const PATCHED_PROTOS = new WeakSet<object>();
if (typeof Element !== "undefined") {
  const proto = Element.prototype as unknown as {
    attachShadow: (init: ShadowRootInit) => ShadowRoot | null;
  };
  if (!PATCHED_PROTOS.has(proto)) {
    const original = proto.attachShadow;
    const patched = function patched(this: Element, init: ShadowRootInit): ShadowRoot | null {
      const root = original.call(this, init);
      if (root) adoptInto(root);
      return root;
    };
    proto.attachShadow = patched;
    PATCHED_PROTOS.add(proto);
  }
}

// Trap the ``adoptedStyleSheets`` setter so Lit (and Shoelace) can't
// wipe the icon sheet when they assign their own. Lit's ``adoptStyles``
// does ``renderRoot.adoptedStyleSheets = styles.map(...)`` — a full
// replacement, not a merge. Without this trap, the icon sheet is added
// by our ``attachShadow`` patch and then immediately overwritten.
type AdoptableRoot = { adoptedStyleSheets: CSSStyleSheet[] };
function protectAdoptedSheets(proto: AdoptableRoot & object): void {
  if (PATCHED_PROTOS.has(proto)) return;
  const descriptor = Object.getOwnPropertyDescriptor(proto, "adoptedStyleSheets");
  if (!descriptor) return;
  const originalSet = descriptor.set;
  const originalGet = descriptor.get;
  const newDescriptor: PropertyDescriptor = {
    configurable: true,
    enumerable: descriptor.enumerable,
    get(this: AdoptableRoot): CSSStyleSheet[] {
      if (originalGet) return originalGet.call(this);
      return (this as { adoptedStyleSheets: CSSStyleSheet[] }).adoptedStyleSheets;
    },
    set(this: AdoptableRoot, value: CSSStyleSheet[]) {
      const sheet = getIconSheet();
      const incoming = value ?? [];
      const hasSheet = incoming.includes(sheet);
      const next = hasSheet ? incoming : [sheet, ...incoming];
      if (originalSet) {
        originalSet.call(this, next);
      } else {
        (this as { adoptedStyleSheets: CSSStyleSheet[] }).adoptedStyleSheets = next;
      }
    },
  };
  Object.defineProperty(proto, "adoptedStyleSheets", newDescriptor);
  PATCHED_PROTOS.add(proto);
}

if (typeof ShadowRoot !== "undefined") {
  protectAdoptedSheets(ShadowRoot.prototype);
}
if (typeof Document !== "undefined") {
  protectAdoptedSheets(Document.prototype);
}

export function ensureIconCss(): void {
  inject();
}

// Safe name validator: ``ti-`` prefix + lowercase alphanum + dashes,
// 2..40 chars. Anything else gets dropped (avoids accidental CSS
// injection if an upstream string is tainted).
const SAFE = /^[a-z][a-z0-9-]{1,39}$/;

/** Returns a complete ``<i class="ti ti-X"></i>`` element string. */
export function tablerIcon(name: string): string {
  if (!SAFE.test(name)) return "";
  return `<i class="ti ti-${name}" aria-hidden="true"></i>`;
}

/** Returns just the icon class name (``ti-X``), no font-family class.
 *  Use this when you already provide the ``ti`` font-family class on
 *  the parent (avoids the redundant ``class="ti ti ti-X"`` produced
 *  by the previous two-class helper). */
export function tablerClass(name: string): string {
  if (!SAFE.test(name)) return "";
  return `ti-${name}`;
}

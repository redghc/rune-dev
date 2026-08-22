// Tabler Icons — lightweight wrapper around @tabler/icons-webfont.
//
// The webfont package ships ``.ttf`` + ``.woff`` + ``.woff2`` + a CSS
// file referencing all three. We deliberately skip the bundled CSS
// (which forces Vite-singlefile to inline all three fonts as base64,
// bloating the bundle by ~5MB) and emit our own minimal CSS that only
// references the ``.woff2`` (~455KB → ~607KB base64). The browser
// ignores unsupported formats so we lose nothing visually.
//
// Usage:
//   import { tablerIcon } from "@/components/ui/icon.js";
//   html`<span class="icon">${tablerIcon("remote")}</span>`
//   html`<rune-icon name="remote"></rune-icon>`

// @ts-expect-error — webfont package has no TS types
import tablerWoff2 from "@tabler/icons-webfont/dist/fonts/tabler-icons.woff2?url";
// ``?raw`` returns the file as a string WITHOUT Vite rewriting any
// ``url(...)`` references — critical because the bundled CSS points
// at woff + ttf + woff2 and ``?inline`` would inline all three fonts.
// @ts-expect-error — webfont package has no TS types
import codepoints from "@tabler/icons-webfont/dist/tabler-icons.css?raw";

let injected = false;

function inject(): void {
  if (injected || typeof document === "undefined") return;
  injected = true;

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

  const style = document.createElement("style");
  style.setAttribute("data-rune", "tabler-icons");
  style.textContent = fontCss;
  document.head.appendChild(style);
}

// Side-effect: inject immediately on module load so consumers never
// need to remember to call a setup fn.
inject();

export function ensureIconCss(): void {
  inject();
}

// Safe name validator: ``ti-`` prefix + lowercase alphanum + dashes,
// 2..40 chars. Anything else gets dropped (avoids accidental CSS
// injection if an upstream string is tainted).
const SAFE = /^[a-z][a-z0-9-]{1,39}$/;

export function tablerIcon(name: string): string {
  if (!SAFE.test(name)) return "";
  return `<i class="ti ti-${name}" aria-hidden="true"></i>`;
}

export function tablerClass(name: string): string {
  if (!SAFE.test(name)) return "";
  return `ti ti-${name}`;
}

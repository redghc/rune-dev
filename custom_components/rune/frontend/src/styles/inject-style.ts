// Inject a ``<style>`` tag into ``document.head`` exactly once.
//
// Both ``root-tokens.ts`` and ``shoelace-theme.ts`` need to drop a
// fixed-id stylesheet into the light DOM (so the cascade reaches
// every Lit shadow root). The mechanics — guard for re-injection, no-op
// when SSR — used to be duplicated in both files.

export function injectStyle(id: string, css: string): void {
  if (typeof document === "undefined") return;
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = css;
  document.head.appendChild(style);
}

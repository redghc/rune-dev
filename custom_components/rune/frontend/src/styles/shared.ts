import { css, unsafeCSS } from "lit";

import { motion, palette, radius, shadow, space, typography } from "./tokens.js";

// Emits CSS custom properties on ``:host`` for both light + dark
// schemes. Light is the default; dark activates via
// ``prefers-color-scheme``. Users can force a theme by adding the
// ``sl-theme-dark`` or ``sl-theme-light`` class to ``documentElement``
// — mirrors Shoelace's selector strategy.

const hostLight = `
  --rune-bg:           ${palette.neutral[50]};
  --rune-bg-elevated:  ${palette.neutral[0]};
  --rune-surface:      ${palette.neutral[0]};
  --rune-surface-alt:  ${palette.neutral[100]};
  --rune-border:       ${palette.neutral[200]};
  --rune-border-strong:${palette.neutral[300]};

  --rune-text:         ${palette.neutral[900]};
  --rune-text-strong:  ${palette.neutral[1000]};
  --rune-text-muted:   ${palette.neutral[600]};
  --rune-text-subtle:  ${palette.neutral[500]};
  --rune-text-inverse: ${palette.neutral[0]};

  --rune-primary:        ${palette.primary[600]};
  --rune-primary-hover:  ${palette.primary[700]};
  --rune-primary-active: ${palette.primary[800]};
  --rune-primary-soft:   ${palette.primary[50]};
  --rune-primary-text:   ${palette.primary[700]};
  --rune-on-primary:     ${palette.neutral[0]};

  --rune-success:        ${palette.success[600]};
  --rune-success-soft:   ${palette.success[50]};
  --rune-success-text:   ${palette.success[700]};

  --rune-warning:        ${palette.warning[600]};
  --rune-warning-soft:   ${palette.warning[50]};
  --rune-warning-text:   ${palette.warning[700]};

  --rune-danger:         ${palette.danger[600]};
  --rune-danger-soft:    ${palette.danger[50]};
  --rune-danger-text:    ${palette.danger[700]};

  --rune-focus-ring: 0 0 0 3px ${palette.primary[200]};

  /* Legacy aliases — kept until existing components migrate to --rune-*. */
  --primary:    ${palette.primary[600]};
  --bg:         ${palette.neutral[50]};
  --bg-2:       ${palette.neutral[100]};
  --card:       ${palette.neutral[0]};
  --text:       ${palette.neutral[900]};
  --muted:      ${palette.neutral[600]};
  --border:     ${palette.neutral[200]};
  --danger:     ${palette.danger[600]};
  --ok:         ${palette.success[600]};
  --warn:       ${palette.warning[600]};
`;

const hostDark = `
  --rune-bg:           ${palette.neutral[950]};
  --rune-bg-elevated:  ${palette.neutral[900]};
  --rune-surface:      ${palette.neutral[900]};
  --rune-surface-alt:  ${palette.neutral[800]};
  --rune-border:       ${palette.neutral[800]};
  --rune-border-strong:${palette.neutral[700]};

  --rune-text:         ${palette.neutral[100]};
  --rune-text-strong:  ${palette.neutral[0]};
  --rune-text-muted:   ${palette.neutral[400]};
  --rune-text-subtle:  ${palette.neutral[500]};
  --rune-text-inverse: ${palette.neutral[900]};

  --rune-primary:        ${palette.primary[400]};
  --rune-primary-hover:  ${palette.primary[300]};
  --rune-primary-active: ${palette.primary[200]};
  --rune-primary-soft:   ${palette.primary[950]};
  --rune-primary-text:   ${palette.primary[300]};
  --rune-on-primary:     ${palette.neutral[950]};

  --rune-success:        ${palette.success[400]};
  --rune-success-soft:   ${palette.success[950]};
  --rune-success-text:   ${palette.success[300]};

  --rune-warning:        ${palette.warning[400]};
  --rune-warning-soft:   ${palette.warning[950]};
  --rune-warning-text:   ${palette.warning[300]};

  --rune-danger:         ${palette.danger[400]};
  --rune-danger-soft:    ${palette.danger[950]};
  --rune-danger-text:    ${palette.danger[300]};

  --rune-focus-ring: 0 0 0 3px ${palette.primary[800]};

  /* Legacy aliases — kept until existing components migrate to --rune-*. */
  --primary:    ${palette.primary[400]};
  --bg:         ${palette.neutral[950]};
  --bg-2:       ${palette.neutral[900]};
  --card:       ${palette.neutral[900]};
  --text:       ${palette.neutral[100]};
  --muted:      ${palette.neutral[400]};
  --border:     ${palette.neutral[800]};
  --danger:     ${palette.danger[400]};
  --ok:         ${palette.success[400]};
  --warn:       ${palette.warning[400]};
`;

export const sharedStyles = css`
  :host {
    ${unsafeCSS(hostLight)}

    --rune-font: ${unsafeCSS(typography.family)};
    --rune-font-mono: ${unsafeCSS(typography.mono)};

    --rune-fs-xs: ${unsafeCSS(typography.size.xs)};
    --rune-fs-sm: ${unsafeCSS(typography.size.sm)};
    --rune-fs-md: ${unsafeCSS(typography.size.md)};
    --rune-fs-lg: ${unsafeCSS(typography.size.lg)};
    --rune-fs-xl: ${unsafeCSS(typography.size.xl)};
    --rune-fs-2xl: ${unsafeCSS(typography.size["2xl"])};
    --rune-fs-3xl: ${unsafeCSS(typography.size["3xl"])};

    --rune-fw-regular: ${unsafeCSS(typography.weight.regular)};
    --rune-fw-medium: ${unsafeCSS(typography.weight.medium)};
    --rune-fw-semibold: ${unsafeCSS(typography.weight.semibold)};
    --rune-fw-bold: ${unsafeCSS(typography.weight.bold)};

    --rune-lh-tight: ${unsafeCSS(typography.leading.tight)};
    --rune-lh-normal: ${unsafeCSS(typography.leading.normal)};
    --rune-lh-relaxed: ${unsafeCSS(typography.leading.relaxed)};

    --rune-space-0: ${unsafeCSS(space[0])};
    --rune-space-1: ${unsafeCSS(space[1])};
    --rune-space-2: ${unsafeCSS(space[2])};
    --rune-space-3: ${unsafeCSS(space[3])};
    --rune-space-4: ${unsafeCSS(space[4])};
    --rune-space-5: ${unsafeCSS(space[5])};
    --rune-space-6: ${unsafeCSS(space[6])};
    --rune-space-7: ${unsafeCSS(space[7])};
    --rune-space-8: ${unsafeCSS(space[8])};

    --rune-radius-xs: ${unsafeCSS(radius.xs)};
    --rune-radius-sm: ${unsafeCSS(radius.sm)};
    --rune-radius-md: ${unsafeCSS(radius.md)};
    --rune-radius-lg: ${unsafeCSS(radius.lg)};
    --rune-radius-xl: ${unsafeCSS(radius.xl)};
    --rune-radius-full: ${unsafeCSS(radius.full)};

    --rune-shadow-1: ${unsafeCSS(shadow[1])};
    --rune-shadow-2: ${unsafeCSS(shadow[2])};
    --rune-shadow-3: ${unsafeCSS(shadow[3])};
    --rune-shadow-4: ${unsafeCSS(shadow[4])};

    --rune-dur-fast: ${unsafeCSS(motion.duration.fast)};
    --rune-dur: ${unsafeCSS(motion.duration.normal)};
    --rune-dur-slow: ${unsafeCSS(motion.duration.slow)};
    --rune-ease: ${unsafeCSS(motion.easing.standard)};

    font-family: var(--rune-font);
    color: var(--rune-text);
    box-sizing: border-box;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }

  @media (prefers-color-scheme: dark) {
    :host(:not(.sl-theme-light)) {
      ${unsafeCSS(hostDark)}
    }
  }

  :host(.sl-theme-dark) {
    ${unsafeCSS(hostDark)}
  }

  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }

  :focus-visible {
    outline: none;
    box-shadow: var(--rune-focus-ring);
  }

  @media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
`;

// Global :root tokens (used by index.html + shim.ts) for the document
// level so bare elements (body, native dialogs, scrollbars) inherit.
export const rootTokensLight = `:root{${hostLight}}`;
export const rootTokensDark = `:root{${hostDark}}`;

export const rootMediaDark = `@media (prefers-color-scheme: dark){:root{${hostDark}}}`;

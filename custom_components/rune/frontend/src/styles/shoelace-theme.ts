// Shoelace 2.x theme overrides — maps our tokens (tokens.ts) onto
// Shoelace's ``--sl-*`` design tokens so every Shoelace component
// inherits the same palette/typography/elevation as our hand-rolled
// Lit components.
//
// Light + dark auto-switch via ``prefers-color-scheme``. Users can also
// force a theme by adding ``sl-theme-light`` or ``sl-theme-dark`` to
// ``<html>``.

import { palette, radius, shadow, space, typography } from "./tokens.js";

const lightPrimary = palette.primary[600];
const lightPrimaryHover = palette.primary[700];
const lightPrimaryActive = palette.primary[800];

const darkPrimary = palette.primary[400];
const darkPrimaryHover = palette.primary[300];
const darkPrimaryActive = palette.primary[200];

export const shoelaceThemeCss = `
:root, .sl-theme-light, .sl-theme-dark {
  --sl-color-primary-50: ${palette.primary[50]};
  --sl-color-primary-100: ${palette.primary[100]};
  --sl-color-primary-200: ${palette.primary[200]};
  --sl-color-primary-300: ${palette.primary[300]};
  --sl-color-primary-400: ${palette.primary[400]};
  --sl-color-primary-500: ${palette.primary[500]};
  --sl-color-primary-600: ${palette.primary[600]};
  --sl-color-primary-700: ${palette.primary[700]};
  --sl-color-primary-800: ${palette.primary[800]};
  --sl-color-primary-900: ${palette.primary[900]};
  --sl-color-primary-950: ${palette.primary[950]};

  --sl-color-neutral-0: ${palette.neutral[0]};
  --sl-color-neutral-50: ${palette.neutral[50]};
  --sl-color-neutral-100: ${palette.neutral[100]};
  --sl-color-neutral-200: ${palette.neutral[200]};
  --sl-color-neutral-300: ${palette.neutral[300]};
  --sl-color-neutral-400: ${palette.neutral[400]};
  --sl-color-neutral-500: ${palette.neutral[500]};
  --sl-color-neutral-600: ${palette.neutral[600]};
  --sl-color-neutral-700: ${palette.neutral[700]};
  --sl-color-neutral-800: ${palette.neutral[800]};
  --sl-color-neutral-900: ${palette.neutral[900]};
  --sl-color-neutral-950: ${palette.neutral[950]};
  --sl-color-neutral-1000: ${palette.neutral[1000]};

  --sl-color-success-600: ${palette.success[600]};
  --sl-color-warning-600: ${palette.warning[600]};
  --sl-color-danger-600: ${palette.danger[600]};

  --sl-font-sans: ${typography.family};
  --sl-font-mono: ${typography.mono};
  --sl-font-size-small: ${typography.size.sm};
  --sl-font-size-medium: ${typography.size.md};
  --sl-font-size-large: ${typography.size.lg};

  --sl-border-radius-small: ${radius.sm};
  --sl-border-radius-medium: ${radius.md};
  --sl-border-radius-large: ${radius.lg};

  --sl-shadow-small: ${shadow[1]};
  --sl-shadow-medium: ${shadow[2]};
  --sl-shadow-large: ${shadow[3]};

  --sl-input-spacing-small: ${space[2]};
  --sl-input-spacing-medium: ${space[2]};
  --sl-input-spacing-large: ${space[3]};
}

:root, .sl-theme-light {
  --sl-color-primary-600: ${lightPrimary};
  --sl-color-primary-700: ${lightPrimaryHover};
  --sl-color-primary-800: ${lightPrimaryActive};
}

.sl-theme-dark {
  --sl-color-primary-600: ${darkPrimary};
  --sl-color-primary-700: ${darkPrimaryHover};
  --sl-color-primary-800: ${darkPrimaryActive};
}

@media (prefers-color-scheme: dark) {
  :root:not(.sl-theme-light) {
    --sl-color-primary-600: ${darkPrimary};
    --sl-color-primary-700: ${darkPrimaryHover};
    --sl-color-primary-800: ${darkPrimaryActive};
  }
}
`;

if (typeof document !== "undefined") {
  const id = "rune-shoelace-theme";
  if (!document.getElementById(id)) {
    const style = document.createElement("style");
    style.id = id;
    style.textContent = shoelaceThemeCss;
    document.head.appendChild(style);
  }
}

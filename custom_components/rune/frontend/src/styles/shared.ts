import { css, unsafeCSS } from "lit";

import { motion, radius, shadow, space, typography } from "./tokens.js";

// Color tokens are defined once on ``:root`` (see ``rootTokens`` at the
// bottom of this file) and injected into ``document.head`` at boot. They
// cascade naturally into every Lit shadow root via custom property
// inheritance — no ``:host`` defaults, no ``:host-context()`` acrobatics.
//
// The root-level rules use ``:root`` + ``:root.sl-theme-dark`` + an
// ``@media (prefers-color-scheme: dark)`` fallback for auto mode. ``state/theme.ts``
// toggles the class on ``documentElement`` when the user picks
// Light / Dark; Auto leaves the class off so the OS media query takes
// over. Shoelace's own palette rides the same ``sl-theme-*`` classes so
// the two systems stay in lockstep.

export const rootTokens = `
  :root {
    --rune-bg:           #f8fafc;
    --rune-bg-elevated:  #ffffff;
    --rune-surface:      #ffffff;
    --rune-surface-alt:  #f1f5f9;
    --rune-border:       #e2e8f0;
    --rune-border-strong:#cbd5e1;

    --rune-text:         #0f172a;
    --rune-text-strong:  #000000;
    --rune-text-muted:   #475569;
    --rune-text-subtle:  #64748b;
    --rune-text-inverse: #ffffff;

    --rune-primary:        #0061d1;
    --rune-primary-hover:  #004ba8;
    --rune-primary-active: #003a82;
    --rune-primary-soft:   #e7f3ff;
    --rune-primary-text:   #004ba8;
    --rune-on-primary:     #ffffff;

    --rune-success:        #059669;
    --rune-success-soft:   #ecfdf5;
    --rune-success-text:   #047857;

    --rune-warning:        #d97706;
    --rune-warning-soft:   #fffbeb;
    --rune-warning-text:   #b45309;

    --rune-danger:         #dc2626;
    --rune-danger-soft:    #fef2f2;
    --rune-danger-text:    #b91c1c;

    --rune-focus-ring: 0 0 0 3px #90c8ff;

    /* Legacy aliases — kept until existing components migrate to --rune-*. */
    --primary:    #0061d1;
    --bg:         #f8fafc;
    --bg-2:       #f1f5f9;
    --card:       #ffffff;
    --text:       #0f172a;
    --muted:      #475569;
    --border:     #e2e8f0;
    --danger:     #dc2626;
    --ok:         #059669;
    --warn:       #d97706;

    color-scheme: light;
  }

  :root.sl-theme-dark {
    --rune-bg:           #020617;
    --rune-bg-elevated:  #0f172a;
    --rune-surface:      #0f172a;
    --rune-surface-alt:  #1e293b;
    --rune-border:       #1e293b;
    --rune-border-strong:#334155;

    --rune-text:         #f1f5f9;
    --rune-text-strong:  #ffffff;
    --rune-text-muted:   #94a3b8;
    --rune-text-subtle:  #64748b;
    --rune-text-inverse: #0f172a;

    --rune-primary:        #2e95ff;
    --rune-primary-hover:  #5aafff;
    --rune-primary-active: #90c8ff;
    --rune-primary-soft:   #001a3d;
    --rune-primary-text:   #5aafff;
    --rune-on-primary:     #020617;

    --rune-success:        #10b981;
    --rune-success-soft:   #022c22;
    --rune-success-text:   #34d399;

    --rune-warning:        #f59e0b;
    --rune-warning-soft:   #451a03;
    --rune-warning-text:   #fbbf24;

    --rune-danger:         #ef4444;
    --rune-danger-soft:    #450a0a;
    --rune-danger-text:    #f87171;

    --rune-focus-ring: 0 0 0 3px #003a82;

    --primary:    #2e95ff;
    --bg:         #020617;
    --bg-2:       #0f172a;
    --card:       #0f172a;
    --text:       #f1f5f9;
    --muted:      #94a3b8;
    --border:     #1e293b;
    --danger:     #ef4444;
    --ok:         #10b981;
    --warn:       #f59e0b;

    color-scheme: dark;
  }

  /* Auto-mode dark: OS prefers dark AND user hasn't forced light. */
  @media (prefers-color-scheme: dark) {
    :root:not(.sl-theme-light) {
      --rune-bg:           #020617;
      --rune-bg-elevated:  #0f172a;
      --rune-surface:      #0f172a;
      --rune-surface-alt:  #1e293b;
      --rune-border:       #1e293b;
      --rune-border-strong:#334155;

      --rune-text:         #f1f5f9;
      --rune-text-strong:  #ffffff;
      --rune-text-muted:   #94a3b8;
      --rune-text-subtle:  #64748b;
      --rune-text-inverse: #0f172a;

      --rune-primary:        #2e95ff;
      --rune-primary-hover:  #5aafff;
      --rune-primary-active: #90c8ff;
      --rune-primary-soft:   #001a3d;
      --rune-primary-text:   #5aafff;
      --rune-on-primary:     #020617;

      --rune-success:        #10b981;
      --rune-success-soft:   #022c22;
      --rune-success-text:   #34d399;

      --rune-warning:        #f59e0b;
      --rune-warning-soft:   #451a03;
      --rune-warning-text:   #fbbf24;

      --rune-danger:         #ef4444;
      --rune-danger-soft:    #450a0a;
      --rune-danger-text:    #f87171;

      --rune-focus-ring: 0 0 0 3px #003a82;

      --primary:    #2e95ff;
      --bg:         #020617;
      --bg-2:       #0f172a;
      --card:       #0f172a;
      --text:       #f1f5f9;
      --muted:      #94a3b8;
      --border:     #1e293b;
      --danger:     #ef4444;
      --ok:         #10b981;
      --warn:       #f59e0b;

      color-scheme: dark;
    }
  }
`;

// Per-component layout / typography / spacing tokens. These don't change
// with the theme so they live in the shared stylesheet that every Lit
// component pulls in via ``static styles = [sharedStyles, ...]``.
export const sharedStyles = css`
  :host {
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

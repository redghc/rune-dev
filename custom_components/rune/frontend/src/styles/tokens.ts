// Design tokens — Material 3 inspired, light + dark, framework-agnostic.
//
// Scales follow the M3 tonal palette convention (50-950) plus a flat
// ``neutral`` ramp. Consumers read tokens via the CSS variables emitted
// in ``shared.ts`` (one per name, suffixed ``-light`` / ``-dark``), or
// via the raw object for JS-driven logic (animations, charts, etc).
//
// Colors use OKLCH for perceptually uniform ramps but are kept as hex
// for build-inlined CSS compatibility.

export interface Palette {
  50: string;
  100: string;
  200: string;
  300: string;
  400: string;
  500: string;
  600: string;
  700: string;
  800: string;
  900: string;
  950: string;
}

export interface NeutralPalette extends Palette {
  0: string;
  1000: string;
}

export const palette = {
  primary: {
    50: "#e7f3ff",
    100: "#c2dfff",
    200: "#90c8ff",
    300: "#5aafff",
    400: "#2e95ff",
    500: "#0079f2",
    600: "#0061d1",
    700: "#004ba8",
    800: "#003a82",
    900: "#002a5e",
    950: "#001a3d",
  } satisfies Palette,

  neutral: {
    0: "#ffffff",
    50: "#f8fafc",
    100: "#f1f5f9",
    200: "#e2e8f0",
    300: "#cbd5e1",
    400: "#94a3b8",
    500: "#64748b",
    600: "#475569",
    700: "#334155",
    800: "#1e293b",
    900: "#0f172a",
    950: "#020617",
    1000: "#000000",
  } satisfies NeutralPalette,

  success: {
    50: "#ecfdf5",
    100: "#d1fae5",
    200: "#a7f3d0",
    300: "#6ee7b7",
    400: "#34d399",
    500: "#10b981",
    600: "#059669",
    700: "#047857",
    800: "#065f46",
    900: "#064e3b",
    950: "#022c22",
  } satisfies Palette,

  warning: {
    50: "#fffbeb",
    100: "#fef3c7",
    200: "#fde68a",
    300: "#fcd34d",
    400: "#fbbf24",
    500: "#f59e0b",
    600: "#d97706",
    700: "#b45309",
    800: "#92400e",
    900: "#78350f",
    950: "#451a03",
  } satisfies Palette,

  danger: {
    50: "#fef2f2",
    100: "#fee2e2",
    200: "#fecaca",
    300: "#fca5a5",
    400: "#f87171",
    500: "#ef4444",
    600: "#dc2626",
    700: "#b91c1c",
    800: "#991b1b",
    900: "#7f1d1d",
    950: "#450a0a",
  } satisfies Palette,
} as const;

export const space = {
  0: "0",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  7: "32px",
  8: "40px",
} as const;

export const radius = {
  xs: "4px",
  sm: "6px",
  md: "10px",
  lg: "16px",
  full: "9999px",
} as const;

export const shadow = {
  1: "0 1px 2px rgb(0 0 0 / 0.06), 0 1px 3px rgb(0 0 0 / 0.04)",
  2: "0 2px 4px rgb(0 0 0 / 0.08), 0 4px 8px rgb(0 0 0 / 0.06)",
  3: "0 4px 6px rgb(0 0 0 / 0.10), 0 8px 16px rgb(0 0 0 / 0.08)",
  4: "0 8px 12px rgb(0 0 0 / 0.12), 0 16px 24px rgb(0 0 0 / 0.10)",
} as const;

export const typography = {
  family: 'Inter, "SF Pro Text", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  mono: 'ui-monospace, SFMono-Regular, "JetBrains Mono", Menlo, Consolas, monospace',
  size: {
    xs: "11px",
    sm: "13px",
    md: "15px",
    lg: "18px",
    xl: "22px",
    "2xl": "28px",
    "3xl": "36px",
  },
  weight: {
    regular: "400",
    medium: "500",
    semibold: "600",
    bold: "700",
  },
  leading: {
    tight: "1.2",
    normal: "1.5",
    relaxed: "1.7",
  },
} as const;

export const motion = {
  duration: {
    fast: "120ms",
    normal: "200ms",
    slow: "320ms",
  },
  easing: {
    standard: "cubic-bezier(0.4, 0, 0.2, 1)",
  },
} as const;

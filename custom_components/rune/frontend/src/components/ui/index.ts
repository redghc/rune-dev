// Barrel export — single import path for all UI primitives.
//
// Usage:
//   import "@/components/ui/index.js";
//   // brings in button, input, select, dialog, chip, tooltip, skeleton,
//   // empty-state, icon helpers, floating util.

import "./button.js";
import "./input.js";
import "./select.js";
import "./dialog.js";
import "./chip.js";
import "./tooltip.js";
import "./skeleton.js";
import "./empty-state.js";
import "./rune-icon.js";
import "./theme-toggle.js";
import "./locale-toggle.js";

export { attachFloating } from "./floating.js";
export type { FloatingOptions } from "./floating.js";
export { ensureIconCss, tablerClass, tablerIcon } from "./icon.js";

export { RuneButton, type RuneButtonVariant, type RuneButtonSize } from "./button.js";
export { RuneInput, type RuneInputSize } from "./input.js";
export {
  RuneSelect,
  type RuneSelectOption,
  type AsyncLoader,
  type RuneSelectSize,
} from "./select.js";
export { RuneDialog, type RuneDialogSize } from "./dialog.js";
export { RuneChip, type RuneChipVariant } from "./chip.js";
export { RuneTooltip } from "./tooltip.js";
export { RuneSkeleton, type RuneSkeletonVariant } from "./skeleton.js";
export { RuneEmptyState } from "./empty-state.js";
export { RuneIcon, type RuneIconSize } from "./rune-icon.js";
export { RuneThemeToggle } from "./theme-toggle.js";
export { RuneLocaleToggle } from "./locale-toggle.js";

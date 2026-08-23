// Styles shared across the top-level views (devices / sniffer /
// actions / settings). Lives in its own module so each view pulls in
// the same constants instead of copy-pasting the same CSS block.

import { css } from "lit";

export const toolbarStyles = css`
  .toolbar {
    display: flex;
    gap: var(--rune-space-3);
    align-items: center;
    margin-bottom: var(--rune-space-5);
  }
  .toolbar h2 {
    margin: 0;
    font-size: var(--rune-fs-2xl);
    font-weight: var(--rune-fw-semibold);
    letter-spacing: -0.02em;
    color: var(--rune-text-strong);
  }
  .grow {
    flex: 1;
  }
  .help {
    margin-bottom: var(--rune-space-4);
    color: var(--rune-text-muted);
    font-size: var(--rune-fs-sm);
  }
  .help i {
    color: var(--rune-primary);
    margin-right: var(--rune-space-1);
    vertical-align: -2px;
  }
`;

export const entityCardStyles = css`
  .entities {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: var(--rune-space-2);
  }
  .entity {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--rune-space-3) var(--rune-space-4);
    background: var(--rune-surface);
    border: 1px solid var(--rune-border);
    border-radius: var(--rune-radius-sm);
    font-family: var(--rune-font-mono);
    font-size: var(--rune-fs-xs);
  }
  .entity-id {
    color: var(--rune-text-strong);
    font-weight: var(--rune-fw-medium);
  }
  .entity-state {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--rune-text-muted);
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: var(--rune-radius-full);
    background: var(--rune-success);
    box-shadow: 0 0 0 3px var(--rune-success-soft);
  }
  .dot.off {
    background: var(--rune-text-subtle);
    box-shadow: 0 0 0 3px var(--rune-surface-alt);
  }
`;

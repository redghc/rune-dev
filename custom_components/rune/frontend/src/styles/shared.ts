import { css } from "lit";

// Shared design tokens + layout primitives. Every Lit component
// imports this via ``static styles = [sharedStyles, css`...`]``.

export const sharedStyles = css`
  :host {
    --primary: #03a9f4;
    --bg: #1f1f1f;
    --bg-2: #252525;
    --card: #2c2c2c;
    --text: #e1e1e1;
    --muted: #9aa0a6;
    --border: #3a3a3a;
    --danger: #f44336;
    --ok: #4caf50;
    --warn: #ff9800;
    font-family: Roboto, "Helvetica Neue", sans-serif;
    color: var(--text);
    box-sizing: border-box;
  }

  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }

  button {
    background: var(--primary);
    color: white;
    border: 0;
    padding: 8px 14px;
    border-radius: 4px;
    cursor: pointer;
    font: inherit;
    font-size: 13px;
  }
  button.secondary {
    background: transparent;
    color: var(--primary);
    border: 1px solid var(--primary);
  }
  button.danger {
    background: var(--danger);
  }
  button.warn {
    background: var(--warn);
  }
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  input,
  select,
  textarea {
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px;
    border-radius: 4px;
    font: inherit;
    font-size: 13px;
    width: 100%;
  }

  label {
    font-size: 12px;
    color: var(--muted);
    display: block;
    margin-bottom: 4px;
  }

  .empty {
    text-align: center;
    padding: 60px 20px;
    color: var(--muted);
    border: 2px dashed var(--border);
    border-radius: 8px;
  }

  .help {
    background: var(--bg-2);
    border-left: 3px solid var(--primary);
    padding: 10px 14px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 12px;
  }
  .help code {
    background: var(--bg);
    padding: 1px 5px;
    border-radius: 3px;
  }
`;

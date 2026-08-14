"""Capture-denoising helpers.

Two operations:

- :func:`split_repeats` — split a captured pulse train into the
  repeated frames that compose it. Used by the Mercator denoise path
  for fussy Manchester remotes whose captures contain noisy repeats.
- :func:`consensus` — return the most-common frame as a cell-string
  ``"HHll..."``. The matcher's ``frame_cells`` helper.
"""
from __future__ import annotations

from collections import Counter

from custom_components.rune.const import IDLE_TRIM_US

# A gap longer than this separates repeated frames inside one capture.
_FRAME_GAP_US = 1300
# A pulse/gap at least this long counts as two cells (H or l).
_LONG_US = 600


def trim_idle_for_quality(timings: list[int]) -> list[int]:
    """Same as ``encoding.timing.trim_idle`` — kept here to avoid the
    cross-package import in callers that only need the consensus path.
    """
    sanitized = [int(t) for t in timings]
    while sanitized and abs(sanitized[0]) > IDLE_TRIM_US:
        sanitized.pop(0)
    while sanitized and abs(sanitized[-1]) > IDLE_TRIM_US:
        sanitized.pop()
    return sanitized


def split_repeats(timings: list[int]) -> list[list[int]]:
    """Split a captured pulse train into its repeated frames.

    A gap longer than ``_FRAME_GAP_US`` between two spaces separates
    one frame from the next. The first and last long-idle gaps are
    trimmed before splitting.
    """
    trimmed = trim_idle_for_quality(timings)
    frames: list[list[int]] = []
    current: list[int] = []
    for value in trimmed:
        if value < 0 and abs(value) > _FRAME_GAP_US:
            if current:
                frames.append(current)
                current = []
            continue
        current.append(value)
    if current:
        frames.append(current)
    return frames


def frame_cells(frame: list[int]) -> str:
    """Render one frame as a cell string (``H`` = high cell, ``l`` = low).

    A pulse/gap >= ``_LONG_US`` is two cells; shorter is one cell.
    """
    cells: list[str] = []
    for value in frame:
        count = 2 if abs(value) >= _LONG_US else 1
        cells.append(("H" if value > 0 else "l") * count)
    return "".join(cells)


def consensus(timings: list[int]) -> tuple[str, int, int]:
    """Return ``(most-common cell string, agreeing, total)``.

    Empty inputs return ``("", 0, 0)``. The cell-string form is what
    :func:`domain.identity.sl_pattern.extract_sl_pattern` collapses
    to, so a match here means the consensus frame came from the same
    button as the reference.
    """
    signatures = [frame_cells(f) for f in split_repeats(timings) if f]
    if not signatures:
        return "", 0, 0
    most_common = Counter(signatures).most_common(1)[0]
    return most_common[0], most_common[1], len(signatures)


def clean_frame(timings: list[int], trailing_gap_us: int = -1800) -> list[int]:
    """Return one clean (consensus) frame's actual timings plus a trailing gap.

    The returned timings end on the same space the capture had, with
    a configurable trailing gap appended. Used by the RF replay path
    when ``clean=True`` — Broadlink then repeats this single clean
    frame instead of the noisy multi-frame raw capture.
    """
    frames = [f for f in split_repeats(timings) if f]
    if not frames:
        return []
    signatures = [frame_cells(f) for f in frames]
    target = Counter(signatures).most_common(1)[0][0]
    chosen = frames[signatures.index(target)]
    return [*chosen, trailing_gap_us]

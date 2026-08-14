"""Signal subpackage — pure Python capture normalization and matching.

- ``normalize`` — raw timings → ``NormalizedSignal`` (carries tiered identity).
- ``matcher`` — given an incoming signal and a list of remotes, decide
  which existing signal it belongs to (or none).
- ``quality`` — denoise a noisy capture (consensus vote, idle trim).
"""

"""Encoding subpackage — pure Python conversions between pulse representations.

Three concerns live here:

- ``pronto`` — Pronto hex ⇄ raw signed-microsecond timings.
- ``broadlink`` — LIRC ticks ⇄ Broadlink packed buffer + base64 wrap.
- ``timing`` — trim idle, bounded trailing terminator.

All conversions are deterministic and side-effect free.
"""

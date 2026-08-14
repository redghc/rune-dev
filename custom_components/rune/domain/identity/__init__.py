"""Signal identity subpackage — pure Python matching primitives.

Three tiers of identity, strongest first:

1. ``signal_identity`` — tiered matching across the three tiers.
2. ``byte_hash`` — Pronto byte quantization (tier 2).
3. ``sl_pattern`` — short/long fingerprint (tier 3).

Tier 1 (decoded protocol identity, e.g. ``NEC:0xFB04:0x08``) is the
strongest. Tier 3 (S/L pattern) is the weakest. The matcher picks the
highest tier available on both sides.
"""

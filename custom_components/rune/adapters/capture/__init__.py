"""Capture subpackage — capture session orchestration and providers.

- :mod:`orchestrator` — single-session asyncio lock + listener notifications
  (HAIR's CaptureOrchestrator, ported and trimmed).
- :mod:`providers` — :class:`CaptureProvider` ABC + :class:`MockProvider`
  for tests.
- :mod:`native_ir` — captures from a HA ``InfraredReceiverEntity`` via
  the platform's async API.
- :mod:`broadlink_rf` — wraps :class:`BroadlinkRFReceiver`'s sweep+capture
  as a one-shot capture provider.

Each provider translates its hardware's native capture model into a
:class:`~custom_components.rune.ports.receiver.CapturedPulse`. The
orchestrator owns the session lifecycle and exposes subscribe / cancel.
"""

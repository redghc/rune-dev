"""Capture subpackage — capture session orchestration and providers.

- :mod:`orchestrator` — single-session asyncio lock + listener notifications
  (HAIR's CaptureOrchestrator, ported and trimmed).
- :mod:`providers` — :class:`CaptureProvider` ABC + :class:`MockProvider`
  for tests.
- :mod:`native_ir` — :class:`NativeIRCaptureProvider`, one-shot IR capture
  from a HA ``InfraredReceiverEntity`` (or any receiver the factory
  resolves for IR transport).
- :mod:`broadlink_rf` — :class:`BroadlinkRFCaptureProvider`, one-shot
  Broadlink RF sweep + capture (RF transport; needs a live ``device_api``).

Each provider translates its hardware's native capture model into a
:class:`~custom_components.rune.ports.receiver.CapturedPulse`. The
orchestrator owns the session lifecycle and exposes subscribe / cancel.
"""

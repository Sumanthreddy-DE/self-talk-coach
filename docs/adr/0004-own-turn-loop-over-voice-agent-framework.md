# ADR 0004 – Own turn-based loop over a voice-agent framework

**Status:** Accepted
**Date:** 2026-10-04

The conversation partner is a small Python loop (push-to-talk → faster-whisper → Claude → TTS) with swappable STT/LLM/TTS interfaces, not Pipecat or LiveKit Agents. Both frameworks support our providers and Pipecat even ships a push-to-talk example, but they are built around realtime audio transports and frame pipelines for hands-free bots; our core value is custom turn logic (help ladder timers, hidden partner text, listening-aid logging, per-turn storage) in a turn-based terminal app, which a framework would make harder to express and test. LiveKit additionally needs a server. Revisit if the phone version needs streaming or barge-in. Evidence: `docs/references/2026-10-04-voice-partner-research.md`.

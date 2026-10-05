# ADR 0005 – Deepgram cloud STT for conversations, not local whisper

**Status:** Accepted
**Date:** 2026-10-05

The conversation partner transcribes learner turns with Deepgram Nova-3 (cloud) instead of the repo's local faster-whisper, breaking the local-first default for this feature. Spike S1 (10 sentences with deliberate B1 errors, same speaker and recordings) showed every whisper size silently "correcting" case and ending errors — small 2/10 kept, medium 3/10, large-v3 3/10 — which would make the session report claim errors the learner never fixed, while Deepgram kept 10/10 at 0.9 s per turn and wrote 5/5 correct sentences back unchanged (no invented errors). Because it is fast enough for live use, one Deepgram pass serves both the partner reply and the report; the planned two-pass live/review design was dropped. Cost: learner audio leaves the laptop, and the feature depends on a paid service ($200 signup credit). Local whisper `medium` stays as an offline fallback whose turns are excluded from error findings. ADR 0001 (faster-whisper for self-talk batch transcription) is unaffected. Evidence: `docs/exec-plans/active/2026-10-04-conversation-partner-design.md` § Spike results.

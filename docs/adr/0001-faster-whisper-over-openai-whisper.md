# ADR 0001 – faster-whisper over openai-whisper

**Status:** Accepted
**Date:** 2026-05-28

## Decision

Use `faster-whisper` (CTranslate2 backend) instead of the reference `openai-whisper` package for transcription.

## Why

- ~4× faster on CPU at equivalent model size
- Supports `compute_type="int8"` quantization for further 2× speedup on CPU
- Same model weights, same accuracy (within float-precision noise)
- Sumanth's corpus runs on a Windows laptop without dedicated GPU; this is the only realistic path to overnight-on-CPU transcription of ~5h audio
- VAD filter built-in, which we need for silence-hallucination suppression

## Trade-off

- Smaller community than `openai-whisper`
- Slightly different API; not drop-in compatible

Acceptable: API is wrapped in `transcribe.Transcriber` so the dependency could be swapped later if needed.

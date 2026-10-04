# Research brief — live German conversation partner

**Date:** 2026-10-04
**Purpose:** Input for the voice-partner design (brainstorm 2026-10-04). Evidence, not decisions.
**Method:** GitHub via `gh search` (agent-reach dev route); Reddit/HN via last30days engine (l30), 90-day window.
**Raw evidence:** `claude-lab/research/raw/{ai-conversation-partner-speaking-practice,elevenlabs,azure-tts-german-voice,pipecat,livekit-voice-agent-latency,freeze-when-speaking-foreign-language}-raw.md`

## Context fact checked first

Laptop: i7-1255U, 16 GB RAM, no NVIDIA GPU (checked 2026-10-04). Rules out GPU-first local TTS/LLM for a live loop.

## GitHub findings (stars / license as of 2026-10-04)

| Repo | Stars | License | Relevance |
|---|---|---|---|
| pipecat-ai/pipecat | 16.2k | BSD-2 | Voice-agent framework. Services include `anthropic`, `azure`, `elevenlabs`, `whisper`, `piper`. Official push-to-talk example in `pipecat-ai/pipecat-examples/push-to-talk`. Frame/transport pipeline — built for realtime bots. |
| livekit/agents | 14.5k | — | Needs LiveKit server/room. Too heavy for a terminal app. |
| KoljaB/RealtimeTTS | 4.0k | MIT | Library. Engines: azure, elevenlabs, edge, piper, kokoro, omnivoice, openai, … — ready-made swappable TTS. |
| KoljaB/RealtimeSTT | 10.2k | MIT | Library. faster-whisper + VAD — path to "real first word" detection. |
| echo-loop/Echo-Loop | 4.1k | AGPL-3.0 | English listening app. Method: intensive listening → shadowing → blind listening → retelling → spaced review of hard sentences. Idea source only. |
| cristianodabc/dialekt | 22 | Apache-2.0 | AI tutor with CEFR-level enforcement on tutor output. Idea source. |
| artcc/freelingo | 153 | AGPL-3.0 | Self-hosted learning platform with voice conversation (WebSocket, Kokoro/faster-whisper or OpenAI). Local speech needs NVIDIA GPU. Reference only. |
| debpalash/VoiceStudio | 52.9k | AGPL-3.0 | Local ElevenLabs alternative; README: CPU "fully usable, slower". |
| k2-fsa/OmniVoice | 14.2k | Apache-2.0 | Voice-cloning TTS, 600+ languages; RTF 0.025 figure is GPU. |
| microsoft/VibeVoice | 54.6k | MIT | Frontier voice AI; GPU-oriented. |

No repo found combining surprise-question / freeze training with deliberate listening training.

## Community findings (Reddit / HN)

Thin. Angles on AI conversation partners, ElevenLabs vs Azure, and Pipecat vs LiveKit returned mostly off-topic HN items. Azure TTS: no community signal in window.

- r/languagelearning, "Please beware of AI when learning languages" (2026-09-13, ~1.6k upvotes). Top comment (579): AI speaking practice felt "unbearably sycophantic and corporate in its speech patterns". Counter (209): helped pass French B2 when used to drill specific tenses, get corrections, and note what to bring to a human tutor.
- r/languagelearning routine thread: "If it's lessons that wrap up neatly in 15 minutes, you're probably still in receiving mode, not producing mode."
- ElevenLabs: v4 released 2026-09-28 (HN). r/ElevenLabs complaint: newer voices "sound like the same guy underneath".

## Pricing checked

- Azure Speech free tier (F0): 0.5M neural TTS characters/month (azure.microsoft.com pricing page, 2026-10-04). Paid S0 rate renders dynamically — not captured.
- OpenSpeaker / ai33.pro: $5 per 1M credits; TTS API is async task + poll, no streaming documented; price ~10–20× below official ElevenLabs suggests resold access. Not used.
- Claude Haiku pricing: not yet verified — pin in spec.

## Implications proposed for design

1. Own small loop on top of RealtimeTTS (later RealtimeSTT) rather than Pipecat or LiveKit.
2. Partner persona: no flattery, colloquial, short turns.
3. Check partner output against the existing B1 baseline.
4. Hard-sentence review queue; retelling as comprehension check.
5. TTS choice by ear test (Azure vs ElevenLabs, same sentences), not by community opinion.

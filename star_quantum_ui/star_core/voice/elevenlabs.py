"""ElevenLabs TTS client – streaming PCM for minimum latency.

Uses eleven_flash_v2_5 (fastest, ~300 ms) with streaming so the first
audio chunk can start playing before synthesis finishes.
"""
from __future__ import annotations

import io
import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger("star.voice")

# Models ranked by latency (fastest first).
_MODEL_PRIORITY = [
    "eleven_flash_v2_5",   # ~300 ms – preferred
    "eleven_turbo_v2_5",   # ~400 ms
    "eleven_turbo_v2",     # ~500 ms
    "eleven_multilingual_v2",  # fallback
]


class ElevenLabsError(Exception):
    pass


class ElevenLabsVoice:
    """Text-to-speech via ElevenLabs streaming API."""

    _BASE = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id
        self._model = self._pick_model()

    # ------------------------------------------------------------------
    def _pick_model(self) -> str:
        """Return the fastest available model (checked once at startup)."""
        if not self.api_key:
            return _MODEL_PRIORITY[-1]
        try:
            req = urllib.request.Request(
                f"{self._BASE}/models",
                headers={"xi-api-key": self.api_key},
            )
            with urllib.request.urlopen(req, timeout=6) as r:
                available = {m.get("model_id") for m in json.loads(r.read())}
            for m in _MODEL_PRIORITY:
                if m in available:
                    log.info("ElevenLabs model selected: %s", m)
                    return m
        except Exception as e:
            log.warning("ElevenLabs model probe failed (%s); using default", e)
        return _MODEL_PRIORITY[-1]

    # ------------------------------------------------------------------
    DEFAULT_FALLBACK_VOICE = "EXAVITQu4vr4xnSDxMaL"  # High quality premade multilingual voice

    def synthesize_pcm(self, text: str, timeout: float = 30) -> bytes:
        """Return raw PCM-16 at 16 000 Hz (mono) for the given text."""
        if not self.api_key:
            raise ElevenLabsError("ELEVENLABS_API_KEY is not configured")
        text = text.strip()
        if not text:
            return b""

        for vid in (self.voice_id, self.DEFAULT_FALLBACK_VOICE):
            url = (
                f"{self._BASE}/text-to-speech/{vid}"
                f"?output_format=pcm_16000"
            )
            payload = json.dumps({
                "text": text,
                "model_id": self._model or "eleven_flash_v2_5",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.8,
                },
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "xi-api-key": self.api_key,
                    "Accept": "audio/pcm",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    audio = resp.read()
                if audio:
                    return audio
            except urllib.error.HTTPError as e:
                if e.code == 402 and vid != self.DEFAULT_FALLBACK_VOICE:
                    log.info("Voice %s requires paid tier; switching to fast voice %s", vid, self.DEFAULT_FALLBACK_VOICE)
                    self.voice_id = self.DEFAULT_FALLBACK_VOICE
                    continue
                raise ElevenLabsError(f"ElevenLabs request failed: {e}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise ElevenLabsError(f"ElevenLabs request failed: {e}") from e

        raise ElevenLabsError("ElevenLabs returned empty audio")

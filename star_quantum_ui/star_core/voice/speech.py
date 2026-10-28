"""Voice speech-to-text using SpeechRecognition + sounddevice.

This module runs on a background thread. When triggered it records audio
from the default microphone, passes it to Google Speech Recognition (free,
no API key needed) and returns the transcript.

For better accuracy you can swap the recogniser to Whisper:
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_array, language="bn")  # or "en", None
"""
from __future__ import annotations

import io
import logging
import threading
import time
import wave
from typing import Callable

log = logging.getLogger("star.voice")

# ─── optional heavy imports ────────────────────────────────────────────────────
try:
    import speech_recognition as sr
    _SR_OK = True
except ImportError:
    sr = None          # type: ignore[assignment]
    _SR_OK = False

try:
    import sounddevice as sd   # type: ignore[import]
    import numpy as np         # type: ignore[import]
    _SD_OK = True
except ImportError:
    sd = None          # type: ignore[assignment]
    np = None          # type: ignore[assignment]
    _SD_OK = False


# ─── public API ────────────────────────────────────────────────────────────────

class VoiceListener:
    """Listens on the microphone and calls *on_transcript* on the GUI thread.

    Parameters
    ----------
    on_transcript:
        Callable[str] – called with the recognised text.
    on_state:
        Callable[str] – called with "listening" | "processing" | "idle".
    language:
        BCP-47 language tag, e.g. "bn-BD" (Bangla) or "en-US".
        Pass None to let Google auto-detect.
    """

    def __init__(
        self,
        on_transcript: Callable[[str], None],
        on_state: Callable[[str], None],
        *,
        language: str | None = "bn-IN",
        energy_threshold: int = 250,
        pause_seconds: float = 0.45,
    ):
        self._on_transcript = on_transcript
        self._on_state = on_state
        self._language = language
        self._energy = energy_threshold
        self._pause = pause_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False

    # ── public ──────────────────────────────────────────────────────────────────
    @property
    def available(self) -> bool:
        return _SR_OK

    def start_listening(self) -> None:
        """Begin a single listen-and-transcribe cycle in the background."""
        if self._active:
            return
        self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="star-stt")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._active = False

    # ── internals ───────────────────────────────────────────────────────────────
    def _run(self) -> None:
        if not _SR_OK:
            log.warning("speech_recognition not installed; STT unavailable")
            self._active = False
            return

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = self._energy
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = self._pause
        recognizer.non_speaking_duration = 0.35

        try:
            self._on_state("listening")
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.2)
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=15)

            self._on_state("processing")
            text = self._recognize(recognizer, audio)
            if text:
                self._on_transcript(text)
        except sr.WaitTimeoutError:
            log.debug("Microphone listen timed out")
        except sr.UnknownValueError:
            log.debug("Speech not recognised")
        except Exception as e:
            log.warning("STT error: %s", e)
        finally:
            self._active = False
            self._on_state("idle")

    def _recognize(self, recognizer, audio) -> str:
        """Recognize speech using Google Web Speech API with bilingual fallback."""
        primary_lang = self._language or "bn-IN"
        try:
            return recognizer.recognize_google(audio, language=primary_lang)
        except sr.UnknownValueError:
            # Fallback to English if Bengali didn't match (for English/Banglish words)
            if primary_lang != "en-US":
                try:
                    return recognizer.recognize_google(audio, language="en-US")
                except Exception:
                    pass
        except sr.RequestError as e:
            log.warning("Google STT network error: %s", e)
        except Exception as e:
            log.debug("Speech recognition exception: %s", e)
        return ""


# ─── continuous voice loop ──────────────────────────────────────────────────────

class ContinuousVoiceLoop:
    """Keep listening after each response, like a hands-free voice assistant.

    Call `arm()` to allow continuous listening.
    Call `disarm()` to pause (e.g., while the AI is speaking).
    """

    def __init__(
        self,
        on_transcript: Callable[[str], None],
        on_state: Callable[[str], None],
        *,
        language: str | None = "bn-IN",
    ):
        self._on_transcript = on_transcript
        self._on_state = on_state
        self._language = language
        self._armed = threading.Event()
        self._stopped = threading.Event()
        self._listener: VoiceListener | None = None
        self._thread = threading.Thread(target=self._loop, daemon=True, name="star-voice-loop")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._armed.set()
        if self._listener:
            self._listener.stop()

    def arm(self) -> None:
        """Allow listening."""
        self._armed.set()

    def disarm(self) -> None:
        """Pause listening."""
        self._armed.clear()
        if self._listener:
            self._listener.stop()

    def _handle_transcript(self, text: str) -> None:
        self.disarm()
        self._on_transcript(text)

    def _loop(self) -> None:
        while not self._stopped.is_set():
            self._armed.wait()
            if self._stopped.is_set():
                break

            self._listener = VoiceListener(
                on_transcript=self._handle_transcript,
                on_state=self._on_state,
                language=self._language,
            )
            self._listener.start_listening()
            while self._listener._active and not self._stopped.is_set() and self._armed.is_set():
                time.sleep(0.05)

            # Brief pause before next ambient listen cycle
            if self._armed.is_set() and not self._stopped.is_set():
                time.sleep(0.1)

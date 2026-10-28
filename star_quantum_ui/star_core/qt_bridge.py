"""BridgePort: connects the backend to the real STAR window through star_ui.UIBridge (Qt signals).

Backend code runs on ONE worker thread; every UI call is a Qt signal emit, which Qt queues onto the GUI thread.
Answers, approvals and stop requests come back from the GUI thread through slots on this object.
"""
from __future__ import annotations

import itertools
import queue
import random
import re
import threading
import time
import logging
import os
import tempfile
import wave

from PySide6.QtCore import QObject

from .voice import ElevenLabsError

YES_WORDS = {"yes", "y", "approve", "ok", "okay", "sure", "হাঁ", "হ্যাঁ", "করো", "ঠিক আছে", "অনুমতি", "চালিয়ে যাও", "chalate paro", "thik ache"}
STOP_WORDS = {"stop", "cancel", "থামো", "থামাও", "বাতিল", "thamo", "thamao", "batil", "no", "না", "করো না"}
log = logging.getLogger("star")


class BridgePort(QObject):
    def __init__(self, bridge, voice=None, voice_loop=None):
        super().__init__()
        self.bridge = bridge
        self.inbox: "queue.Queue[str]" = queue.Queue()
        self.approval_tab_id: str | None = None
        self._ids = itertools.count(1)
        self._cancel = threading.Event()
        self._approvals: dict[str, tuple[threading.Event, list]] = {}
        self._asking = False
        self._answer_event = threading.Event()
        self._answer: str | None = None
        self._speech_token = 0
        self.voice = voice
        self.voice_loop = voice_loop
        bridge.user_text.connect(self._on_user_text)
        bridge.tab_action.connect(self._on_tab_action)

    # GUI-thread slots --------------------------------------------------------------------
    def _on_user_text(self, text: str) -> None:
        t = text.strip()
        if not t:
            return
        if self._asking:
            self._answer = t
            self._answer_event.set()
        elif self._approvals:
            low = t.lower()
            tab_id, (ev, res) = next(iter(self._approvals.items()))
            if any(w in low for w in YES_WORDS):
                res.append(True)
                ev.set()
            elif any(w in low for w in STOP_WORDS):
                res.append(False)
                ev.set()
            else:
                self.inbox.put(t)
        elif t.lower() in STOP_WORDS:
            self._cancel.set()
        else:
            self.inbox.put(t)

    def _on_tab_action(self, tab_id: str, action: str, data) -> None:
        pending = self._approvals.get(tab_id)
        if pending is not None and action in ("approve", "cancel"):
            pending[1].append(action == "approve")
            pending[0].set()
        elif action == "stop":
            self._cancel.set()
        elif action == "message" and isinstance(data, str):
            if self._asking:
                self._answer = data
                self._answer_event.set()
            else:
                self.inbox.put(data)

    # worker-thread API (UIPort) -----------------------------------------------------------
    def shutdown(self) -> None:
        """Stop background speech pulses and unblock anything waiting for the user."""
        self._speech_token += 1
        self._cancel.set()
        if self.voice_loop:
            self.voice_loop.stop()

    def reset_cancel(self) -> None:
        self._cancel.clear()

    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def set_state(self, state: str) -> None:
        self.bridge.state.emit(state)

    def say(self, text: str) -> None:
        self._speech_token += 1
        token = self._speech_token
        if self.voice_loop:
            self.voice_loop.disarm()
        self.bridge.message.emit(text)
        self.bridge.state.emit("speaking")
        hold = max(1.8, min(12.0, 0.045 * len(text)))

        def pulse():
            try:
                if self.voice is not None and os.name == "nt":
                    self._play_voice(text)
                end = time.time() + hold
                while time.time() < end and token == self._speech_token:
                    self.bridge.level.emit(0.25 + 0.75 * random.random())
                    time.sleep(0.06)
                if token == self._speech_token:
                    self.bridge.level.emit(-1.0)
                    self.bridge.state.emit("idle")
                    if self.voice_loop:
                        self.voice_loop.arm()
            except RuntimeError:   # the window was closed while we were talking
                pass

        threading.Thread(target=pulse, daemon=True).start()

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        raw = [s.strip() for s in re.split(r'([।?!.\n]+)', text) if s.strip()]
        chunks = []
        i = 0
        while i < len(raw):
            s = raw[i]
            if i + 1 < len(raw) and re.match(r'^[।?!.]+$', raw[i + 1]):
                chunks.append(s + raw[i + 1])
                i += 2
            else:
                chunks.append(s)
                i += 1
        return [c for c in chunks if c.strip()]

    def _play_voice(self, text: str) -> None:
        try:
            import winsound
            sentences = self._split_sentences(text)
            if not sentences:
                sentences = [text]

            audio_queue: "queue.Queue[tuple[str, bytes | None]]" = queue.Queue(maxsize=3)
            stop_fetch = threading.Event()

            def fetcher():
                for s in sentences:
                    if stop_fetch.is_set():
                        break
                    try:
                        pcm = self.voice.synthesize_pcm(s)
                        audio_queue.put((s, pcm))
                    except Exception as e:
                        log.warning("speech chunk fetch failed: %s", e)
                        audio_queue.put((s, None))
                audio_queue.put(("", None))

            threading.Thread(target=fetcher, daemon=True).start()

            while True:
                s, pcm = audio_queue.get()
                if not s:
                    break
                if pcm is None:
                    self._speak_fallback_sapi(s)
                    continue
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    path = f.name
                try:
                    with wave.open(path, "wb") as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(16000)
                        wav.writeframes(pcm)
                    winsound.PlaySound(path, winsound.SND_FILENAME)
                finally:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            stop_fetch.set()
        except Exception as e:
            log.warning("voice reply unavailable via ElevenLabs (%s); falling back to SAPI", e)
            self._speak_fallback_sapi(text)

    def _speak_fallback_sapi(self, text: str) -> None:
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Rate = 1
            speaker.Speak(text)
        except Exception as e:
            log.warning("SAPI fallback error: %s", e)

    def open_tab(self, kind: str, title: str, payload: dict) -> str:
        tab_id = f"{kind}-b{next(self._ids)}"
        self.bridge.tab_open.emit(tab_id, kind, title, payload)
        return tab_id

    def tab_event(self, tab_id: str, event: str, data=None) -> None:
        self.bridge.tab_event.emit(tab_id, event, data)

    def close_tab(self, tab_id: str) -> None:
        self.bridge.tab_close.emit(tab_id)

    def metric(self, name: str, value: float) -> None:
        self.bridge.metric.emit(name, float(value))

    def _wait(self, event: threading.Event, timeout: float | None) -> bool:
        end = time.time() + (timeout or 3600)
        while time.time() < end:
            if event.wait(0.2):
                return True
            if self._cancel.is_set():
                return False
        return False

    def ask(self, question: str, timeout: float | None = None) -> str | None:
        self._answer, self._asking = None, True
        self._answer_event.clear()
        self.bridge.message.emit(question)
        self.bridge.state.emit("speaking")
        if self.voice is not None and os.name == "nt":
            self._play_voice(question)
        self.bridge.state.emit("listening")
        if self.voice_loop:
            self.voice_loop.arm()
        got = self._wait(self._answer_event, timeout)
        if self.voice_loop:
            self.voice_loop.disarm()
        self._asking = False
        return self._answer if got else None

    def request_approval(self, title: str, description: str, info: dict, steps: list[str],
                         timeout: float | None = None, keep_open: bool = False) -> bool:
        tab_id = self.open_tab("system", title, {"heading": title, "description": description,
                                                  "info": {k: str(v) for k, v in info.items()}, "steps": steps})
        event, result = threading.Event(), []
        self._approvals[tab_id] = (event, result)
        self.tab_event(tab_id, "awaiting_approval", None)
        self.bridge.message.emit(description)
        self.bridge.state.emit("speaking")
        if self.voice is not None and os.name == "nt":
            self._play_voice(description)
        self.bridge.state.emit("listening")
        if self.voice_loop:
            self.voice_loop.arm()
        got = self._wait(event, timeout)
        if self.voice_loop:
            self.voice_loop.disarm()
        approved = bool(got and result and result[0])
        self._approvals.pop(tab_id, None)
        if approved and keep_open:
            self.approval_tab_id = tab_id
            return True
        self.approval_tab_id = None
        if approved:  # approved but nothing more to show: close the tab after a moment
            self.tab_event(tab_id, "finished", {"ok": True, "text": "Approved"})
            threading.Timer(1.2, lambda: self.close_tab(tab_id)).start()
        elif not result:  # timed out or cancelled while waiting: remove the tab
            self.close_tab(tab_id)
        return approved

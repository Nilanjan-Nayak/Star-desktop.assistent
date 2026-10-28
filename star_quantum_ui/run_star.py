"""STAR: frontend + backend.

    python run_star.py                 normal: local Ollama (cloud fallback if configured)
    python run_star.py --mock-llm      offline test double instead of a real model
    python run_star.py --demo          frontend only, fake assistant (no backend)
    python run_star.py --check         print backend status and exit (no window)
    python run_star.py --home PATH     use another STAR home folder (config, memory, skills)
"""
import argparse
import logging
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import json
from pathlib import Path


def check(config) -> int:
    from star_core.llm import OllamaClient, OpenRouterClient
    print(f"STAR home : {config.home}")
    print(f"Config    : {config.home / 'star_config.json'} ({'exists' if (config.home / 'star_config.json').exists() else 'will be created'})")
    for r in config.roots:
        print(f"Allowed   : {r} {'(ok)' if r.is_dir() else '(missing - create it or edit allowed_roots)'}")
    ol = OllamaClient(config.ollama_url, config.ollama_model)
    print(f"Ollama    : {'ready' if ol.available() else 'not reachable'} ({config.ollama_url}, model {config.ollama_model})")
    key = config.openrouter_api_key
    print(f"OpenRouter: {'key set' if key else 'no key'}; cloud_fallback={config.cloud_fallback}")
    return 0 if ol.available() or (key and config.cloud_fallback) else 1


def start_ollama(config):
    """Start Ollama when needed and return the process owned by this app."""
    from star_core.llm import OllamaClient

    client = OllamaClient(config.ollama_url, config.ollama_model)
    if client.available():
        return None
    executable = shutil.which("ollama")
    if not executable:
        raise RuntimeError("Ollama was not found on PATH. Install Ollama or use --mock-llm.")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        process = subprocess.Popen(
            [executable, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=creationflags)
    except OSError as e:
        raise RuntimeError(f"could not start Ollama: {e}") from e
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(config.ollama_url.rstrip("/") + "/api/tags", timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read())
                    names = [m.get("name", "") for m in data.get("models", [])]
                    if names and not any(
                        n == config.ollama_model or n.split(":")[0] == config.ollama_model.split(":")[0]
                        for n in names
                    ):
                        process.terminate()
                        raise RuntimeError(
                            f"Ollama is running, but model '{config.ollama_model}' is not installed. "
                            f"Run: ollama pull {config.ollama_model}"
                        )
                    return process
        except RuntimeError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            if process.poll() is not None:
                try:
                    with urllib.request.urlopen(config.ollama_url.rstrip("/") + "/api/tags", timeout=1) as resp:
                        if resp.status == 200:
                            return None
                except Exception:
                    pass
                break
        time.sleep(0.5)
    try:
        with urllib.request.urlopen(config.ollama_url.rstrip("/") + "/api/tags", timeout=1) as resp:
            if resp.status == 200:
                if process.poll() is None:
                    process.terminate()
                return None
    except Exception:
        pass
    if process.poll() is None:
        process.terminate()
    raise RuntimeError("Ollama did not become ready within 20 seconds.")


def main() -> int:
    ap = argparse.ArgumentParser(description="STAR assistant")
    ap.add_argument("--mock-llm", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--home", type=Path, default=None)
    ap.add_argument("--no-ollama-autostart", action="store_true",
                    help="do not start Ollama automatically")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    from star_core.config import Config
    config = Config.load(args.home)
    if not (config.home / "star_config.json").exists():
        config.save()
    if args.check:
        return check(config)
    ollama_process = None
    if not args.demo and not args.mock_llm and not args.no_ollama_autostart:
        try:
            ollama_process = start_ollama(config)
        except RuntimeError as e:
            logging.error("%s", e)
            return 1

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from star_ui import DemoDriver, MainWindow, StateModel, UIBridge

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    model, bridge = StateModel(), UIBridge()
    window = MainWindow(model, bridge)
    keep = [model, bridge, window]
    if args.demo:
        keep.append(DemoDriver(bridge))
    else:
        from star_core.app import BackendRunner, build_orchestrator
        from star_core.qt_bridge import BridgePort
        voice = None
        if config.voice_enabled and config.elevenlabs_api_key:
            from star_core.voice import ElevenLabsVoice
            voice = ElevenLabsVoice(config.elevenlabs_api_key, config.elevenlabs_voice_id)

        voice_loop = None
        if config.voice_input_enabled:
            from star_core.voice import ContinuousVoiceLoop
            voice_loop = ContinuousVoiceLoop(
                on_transcript=lambda txt: bridge.user_text.emit(txt),
                on_state=lambda s: bridge.state.emit(s),
                language=config.voice_input_language,
            )
            voice_loop.start()
            QTimer.singleShot(1800, voice_loop.arm)

        port = BridgePort(bridge, voice=voice, voice_loop=voice_loop)
        orch = build_orchestrator(config, port, mock_llm=args.mock_llm)
        runner = BackendRunner(port, orch)
        runner.start()
        app.aboutToQuit.connect(runner.stop)
        if voice_loop is not None:
            app.aboutToQuit.connect(voice_loop.stop)
        if ollama_process is not None:
            app.aboutToQuit.connect(ollama_process.terminate)
        keep += [port, orch, runner, voice_loop, ollama_process]
    window.show()
    app._keep = keep
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

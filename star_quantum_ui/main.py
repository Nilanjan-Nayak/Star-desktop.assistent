"""STAR - Quantum Realm UI.   Run:  python main.py   (add --no-demo when wiring the real core)"""
import sys

from PySide6.QtWidgets import QApplication

from star_ui import DemoDriver, MainWindow, StateModel, UIBridge


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    model, bridge = StateModel(), UIBridge()
    window = MainWindow(model, bridge)
    demo = None if "--no-demo" in sys.argv else DemoDriver(bridge)
    window.show()
    app._keep = (model, bridge, window, demo)  # keep references alive
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

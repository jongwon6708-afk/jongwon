"""Application entry point for the 3D Bone CT Simulator."""

from __future__ import annotations

import sys

from PyQt5 import QtWidgets

from .viewer import ViewerWindow


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = ViewerWindow()
    window.start()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())

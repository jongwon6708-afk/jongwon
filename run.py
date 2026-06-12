"""Launcher: ``python run.py`` starts the 3D Bone CT Simulator GUI."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from bonesim.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

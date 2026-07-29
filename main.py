"""
Entry Point
===========
Bootstraps the PySide6 application, wires the ViewModel to the View,
and starts the Qt event loop.

Usage
-----
From the final_project directory:

    python main.py

Or from the repository root (using uv):

    uv run final_project/main.py
"""

import sys
import os

# Ensure imports resolve from the final_project directory regardless of where
# the script is launched from.
sys.path.insert(0, os.path.dirname(__file__))

from PySide6.QtWidgets import QApplication

from viewmodels.main_view_model import MainViewModel
from views.main_view import MainView


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("EMG Signal Viewer")

    view_model = MainViewModel()
    view = MainView(view_model)
    view.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

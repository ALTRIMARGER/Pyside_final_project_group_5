"""
Offline Inspection Window
=========================
A standalone QMainWindow that opens after streaming stops (or on user request).
It embeds a Matplotlib figure and lets the user inspect the full recorded signal.

Controls
--------
- Channel selector  (QComboBox, Ch 1 … Ch 32)
- Signal mode       (QComboBox, Original / RMS / Filtered)
- "Plot" button     — redraws the selected channel with the chosen mode

The offline plot does NOT update live; it shows a static snapshot of whatever
was recorded in the full_buffer at the moment the window was opened.

Data is received as a tuple (full_buffer, sampling_rate) from the ViewModel's
get_offline_data() method and is never modified here (View responsibility only).
"""

import numpy as np
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from models.signal_processor import process_channel, FILTER_LOW_HZ, FILTER_HIGH_HZ, RMS_WINDOW_MS

NUM_CHANNELS = 32
SIGNAL_MODES = ["Original", "RMS", "Filtered"]


class OfflineInspectionWindow(QMainWindow):
    """
    Matplotlib-based offline signal inspection window.

    Parameters
    ----------
    full_buffer : np.ndarray  shape (channels, N)
        Full recording captured during streaming.
    sampling_rate : float
        Samples per second (from the TCP model).
    parent : QWidget | None
        Optional parent widget.
    """

    def __init__(
        self,
        full_buffer: np.ndarray,
        sampling_rate: float,
        parent=None,
    ):
        super().__init__(parent)

        self._data = full_buffer          # (channels, N) — never modified here
        self._sampling_rate = sampling_rate

        self.setWindowTitle("Offline Signal Inspection — Matplotlib")
        self.resize(1100, 650)

        # ---- central widget + layouts ----------------------------------------
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # ---- control bar -------------------------------------------------------
        controls = QHBoxLayout()
        controls.setSpacing(10)

        controls.addWidget(QLabel("Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.addItems([f"Channel {i + 1}" for i in range(NUM_CHANNELS)])
        controls.addWidget(self._channel_combo)

        controls.addWidget(QLabel("Signal mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(SIGNAL_MODES)
        controls.addWidget(self._mode_combo)

        self._plot_button = QPushButton("Plot")
        controls.addWidget(self._plot_button)

        controls.addStretch()

        # Info label: recording duration
        duration_s = full_buffer.shape[1] / sampling_rate if sampling_rate > 0 else 0.0
        info_text = (
            f"Recording: {full_buffer.shape[1]} samples  |  "
            f"{duration_s:.2f} s  |  {NUM_CHANNELS} channels  |  "
            f"Fs = {sampling_rate:.0f} Hz"
        )
        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet("font-size: 11px; color: #555;")

        main_layout.addLayout(controls)
        main_layout.addWidget(self._info_label)

        # ---- Matplotlib canvas -------------------------------------------------
        self._figure = Figure(figsize=(10, 5), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        main_layout.addWidget(self._canvas, stretch=1)

        # ---- parameter hint label ----------------------------------------------
        hint = (
            f"Signal processing parameters — "
            f"RMS window: {RMS_WINDOW_MS:.0f} ms  |  "
            f"Bandpass: {FILTER_LOW_HZ:.0f}–{FILTER_HIGH_HZ:.0f} Hz  |  "
            f"Filter order: 4 (Butterworth, zero-phase)"
        )
        hint_label = QLabel(hint)
        hint_label.setStyleSheet("font-size: 10px; color: #777;")
        main_layout.addWidget(hint_label)

        # ---- connections -------------------------------------------------------
        self._plot_button.clicked.connect(self._draw_plot)
        self._channel_combo.currentIndexChanged.connect(self._draw_plot)
        self._mode_combo.currentIndexChanged.connect(self._draw_plot)

        # Draw initial plot
        self._draw_plot()

    # ---------------------------------------------------------- private API ---

    def _draw_plot(self) -> None:
        """
        Compute and render the selected channel with the chosen processing mode.

        Steps
        -----
        1. Read the current channel index and mode from the combo boxes.
        2. Extract the raw channel data from the full buffer.
        3. Apply signal processing via ``process_channel()``.
        4. Build a time axis in seconds.
        5. Clear the figure and plot.
        """
        ch = self._channel_combo.currentIndex()
        mode = self._mode_combo.currentText()

        if self._data is None or self._data.shape[1] < 2:
            self._show_error("No data available for offline inspection.")
            return

        raw = self._data[ch, :]

        try:
            y = process_channel(raw, self._sampling_rate, mode)
        except Exception as exc:
            self._show_error(f"Processing error: {exc}")
            return

        n = len(y)
        t = np.arange(n) / self._sampling_rate

        # ---- draw --------------------------------------------------------------
        self._figure.clear()
        ax = self._figure.add_subplot(111)

        ax.plot(t, y, color="#1a5fb4", linewidth=0.8, label=f"{mode} — Channel {ch + 1}")
        ax.set_title(f"Offline Inspection — {mode} — Channel {ch + 1}", fontsize=12)
        ax.set_xlabel("Time (s)", fontsize=10)
        ax.set_ylabel("Amplitude", fontsize=10)
        ax.grid(True, alpha=0.4)
        ax.legend(loc="upper right", fontsize=9)

        self._canvas.draw()

    def _show_error(self, message: str) -> None:
        """Display an error message inside the Matplotlib axes."""
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.text(
            0.5, 0.5, message,
            ha="center", va="center",
            transform=ax.transAxes,
            fontsize=12, color="red",
        )
        self._canvas.draw()

"""
Main ViewModel
==============
Sits between the Model layer (TCP + signal processing) and the View layer (GUI).

Responsibilities
----------------
- Create and own the TcpClientModel.
- Connect / disconnect from the server on user request.
- Drive a QTimer to poll for new TCP data at ~100 Hz (every 10 ms).
- Apply signal processing (Original / RMS / Filtered) before emitting plot data.
- Emit Qt signals so the View never touches the Model directly.
- Track current channel selection and signal mode.
- Provide the full recording buffer to the offline Matplotlib view.

Signals emitted to the View
----------------------------
plot_updated(x, y)              — processed single-channel data for live VisPy plot
all_channels_updated(x, data)   — processed all-channel data for "Plot All Channels"
status_updated(str)             — human-readable connection / error messages
signal_time_updated(float)      — cumulative signal time in seconds
connection_changed(bool)        — True = connected, False = disconnected
"""

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from models.tcp_client_model import TcpClientModel
from models.signal_processor import process_channel, process_all_channels


class MainViewModel(QObject):
    # ---------------------------------------------------------------- signals -

    # Live single-channel plot: (x: np.ndarray, y: np.ndarray)
    plot_updated = Signal(object, object)

    # All-channels overview plot: (x: np.ndarray, data: np.ndarray [channels, N])
    all_channels_updated = Signal(object, object)

    # Status bar / info label text
    status_updated = Signal(str)

    # Cumulative signal time in seconds (drives the time label)
    signal_time_updated = Signal(float)

    # True when connected, False when disconnected
    connection_changed = Signal(bool)

    # ------------------------------------------------------------------ init --

    def __init__(self) -> None:
        super().__init__()

        # TCP client model — default parameters matching the provided server
        self.model = TcpClientModel(
            host="localhost",
            port=12345,
            sampling_rate=2000.0,
            channels=32,
            samples_per_packet=18,
            window_seconds=10.0,
            selected_channel=0,
        )

        # Current UI state
        self._selected_channel: int = 0
        self._signal_mode: str = "Original"   # "Original" | "RMS" | "Filtered"
        self._show_all_channels: bool = False
        self.is_streaming: bool = False

        # QTimer drives the polling loop (~100 Hz = every 10 ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    # ------------------------------------------------------- public actions --

    def connect(self, port: int) -> None:
        """
        Connect to the TCP server on the given port and start streaming.

        Parameters
        ----------
        port : int
            TCP port number entered by the user.
        """
        if self.is_streaming:
            return

        # Update port before connecting
        self.model.port = port
        self.model.reset_buffers()

        try:
            self.model.connect()
        except OSError as error:
            self.status_updated.emit(f"Could not connect: {error}")
            return

        self.is_streaming = True
        self.connection_changed.emit(True)
        self.status_updated.emit(f"Connected to localhost:{port}. Streaming…")
        self._timer.start(10)

    def disconnect(self) -> None:
        """Stop the timer, close the TCP connection, and notify the View."""
        if not self.is_streaming:
            return

        self._timer.stop()
        self.model.disconnect()
        self.is_streaming = False

        self.connection_changed.emit(False)
        self.status_updated.emit("Disconnected. You can now inspect the offline plot.")

    # ------------------------------------------------- channel / mode setters -

    def set_channel(self, channel_index: int) -> None:
        """
        Change the displayed channel for the live single-channel plot.

        Parameters
        ----------
        channel_index : int
            Zero-based channel index (0–31).
        """
        self._selected_channel = channel_index
        self.model.selected_channel = channel_index

    def set_signal_mode(self, mode: str) -> None:
        """
        Set the signal processing mode.

        Parameters
        ----------
        mode : str
            One of ``"Original"``, ``"RMS"``, ``"Filtered"``.
        """
        self._signal_mode = mode

    def set_show_all_channels(self, enabled: bool) -> None:
        """
        Toggle between single-channel and all-channels live view.

        Parameters
        ----------
        enabled : bool
            True  → emit all-channels data each tick.
            False → emit single-channel data each tick.
        """
        self._show_all_channels = enabled

    # -------------------------------------------- offline data for the View --

    def get_offline_data(self):
        """
        Return the full recording buffer for offline Matplotlib inspection.

        Returns
        -------
        tuple[np.ndarray, float] | None
            (full_buffer (channels, N), sampling_rate) if data exists,
            or None if no data has been recorded yet.
        """
        if not self.model.has_full_data():
            return None
        return self.model.full_buffer.copy(), self.model.sampling_rate

    # ----------------------------------------------------------------- timer --

    def _poll(self) -> None:
        """
        Called every 10 ms by the QTimer.

        Steps:
        1. Ask the model to read all available bytes from the socket.
        2. If the model has been disconnected by the server, handle it.
        3. Apply signal processing.
        4. Emit the correct signal depending on the current view mode.
        5. Update the signal time label.
        """
        self.model.receive_data()

        # Detect server-side disconnect
        if not self.model.is_connected and self.is_streaming:
            self._timer.stop()
            self.is_streaming = False
            self.connection_changed.emit(False)
            self.status_updated.emit("Server closed the connection.")
            return

        if not self.model.has_data():
            return

        sampling_rate = self.model.sampling_rate

        if self._show_all_channels:
            # All-channels overview
            x, raw_data = self.model.get_all_channels_window()

            try:
                processed = process_all_channels(raw_data, sampling_rate, self._signal_mode)
            except Exception:
                processed = raw_data

            self.all_channels_updated.emit(x, processed)

        else:
            # Single selected channel
            x, raw_y = self.model.get_window()

            try:
                y = process_channel(raw_y, sampling_rate, self._signal_mode)
            except Exception:
                y = raw_y

            self.plot_updated.emit(x, y)

        # Update signal-time label regardless of view mode
        signal_time = self.model.get_signal_time_seconds()
        self.signal_time_updated.emit(signal_time)

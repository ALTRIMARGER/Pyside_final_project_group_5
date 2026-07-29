"""
Main View
=========
The primary application window.  Contains all user-facing controls and hosts
the VisPy plot widgets.  Follows MVVM: the View only talks to the ViewModel
via method calls and Qt signal connections — it never touches the Model directly.

Layout (left panel + right plot area)
--------------------------------------
Left panel (controls)
  ┌─────────────────────────┐
  │  TCP Connection         │
  │  Port [_____] [Connect] │
  │  [Disconnect]           │
  │  Status: …              │
  ├─────────────────────────┤
  │  Signal Time: 0.00 s    │
  ├─────────────────────────┤
  │  Live Plot Settings     │
  │  Channel [combo]        │
  │  Mode    [combo]        │
  │  Y-scale [spinbox]      │
  ├─────────────────────────┤
  │  [Plot All Channels]    │
  │  [Back to Single Ch.]   │
  ├─────────────────────────┤
  │  Offline Inspection     │
  │  [Open Offline Plot]    │
  └─────────────────────────┘

Right area (stacked VisPy widgets — single-channel OR all-channels)
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from views.plot_view import AllChannelsPlotWidget, SingleChannelPlotWidget
from views.offline_view import OfflineInspectionWindow


NUM_CHANNELS = 32
SIGNAL_MODES = ["Original", "RMS", "Filtered"]
DEFAULT_PORT = 12345
DEFAULT_Y_SCALE = 300.0


class MainView(QMainWindow):
    """
    Main application window.

    Parameters
    ----------
    view_model : MainViewModel
        The ViewModel instance that drives this View.
    """

    def __init__(self, view_model):
        super().__init__()

        self._vm = view_model
        self._offline_window = None   # keep a reference so it is not GC'd

        self.setWindowTitle("EMG Signal Viewer — TCP Live Visualization")
        self.resize(1400, 800)

        # ---- build UI --------------------------------------------------------
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(10)

        root_layout.addWidget(self._build_control_panel(), stretch=0)
        root_layout.addWidget(self._build_plot_area(), stretch=1)

        # ---- connect ViewModel → View signals --------------------------------
        self._vm.status_updated.connect(self._status_label.setText)
        self._vm.signal_time_updated.connect(self._update_time_label)
        self._vm.signal_time_updated.connect(self._single_plot.set_signal_time)
        self._vm.connection_changed.connect(self._on_connection_changed)

        # Live plot data
        self._vm.plot_updated.connect(self._single_plot.update_plot)
        self._vm.all_channels_updated.connect(self._all_plot.update_all_channels)

    # ================================================================ build UI

    def _build_control_panel(self) -> QWidget:
        """Build and return the left control panel widget."""
        panel = QWidget()
        panel.setFixedWidth(240)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # ---- TCP Connection section ------------------------------------------
        layout.addWidget(self._section_label("TCP Connection"))

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self._port_input = QLineEdit(str(DEFAULT_PORT))
        self._port_input.setPlaceholderText("e.g. 12345")
        self._port_input.setMaximumWidth(80)
        port_row.addWidget(self._port_input)
        layout.addLayout(port_row)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self._connect_btn)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setEnabled(False)
        self._disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        layout.addWidget(self._disconnect_btn)

        self._status_label = QLabel("Not connected.")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self._status_label)

        layout.addWidget(self._divider())

        # ---- Signal time -----------------------------------------------------
        self._time_label = QLabel("Signal time: 0.00 s")
        self._time_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self._time_label)

        layout.addWidget(self._divider())

        # ---- Live plot settings ----------------------------------------------
        layout.addWidget(self._section_label("Live Plot Settings"))

        layout.addWidget(QLabel("Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.addItems([f"Channel {i + 1}" for i in range(NUM_CHANNELS)])
        self._channel_combo.currentIndexChanged.connect(self._on_channel_changed)
        layout.addWidget(self._channel_combo)

        layout.addWidget(QLabel("Signal mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(SIGNAL_MODES)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self._mode_combo)

        layout.addWidget(QLabel("Y-scale (±):"))
        self._y_scale_spin = QDoubleSpinBox()
        self._y_scale_spin.setRange(1.0, 1_000_000.0)
        self._y_scale_spin.setValue(DEFAULT_Y_SCALE)
        self._y_scale_spin.setSingleStep(50.0)
        self._y_scale_spin.setDecimals(1)
        self._y_scale_spin.valueChanged.connect(self._on_y_scale_changed)
        layout.addWidget(self._y_scale_spin)

        layout.addWidget(self._divider())

        # ---- All-channels / back buttons ------------------------------------
        self._all_channels_btn = QPushButton("Plot All Channels")
        self._all_channels_btn.clicked.connect(self._on_plot_all_channels)
        layout.addWidget(self._all_channels_btn)

        self._single_ch_btn = QPushButton("Back to Single Channel")
        self._single_ch_btn.setEnabled(False)
        self._single_ch_btn.clicked.connect(self._on_back_to_single)
        layout.addWidget(self._single_ch_btn)

        layout.addWidget(self._divider())

        # ---- Offline inspection ----------------------------------------------
        layout.addWidget(self._section_label("Offline Inspection"))

        self._offline_btn = QPushButton("Open Offline Plot")
        self._offline_btn.clicked.connect(self._on_open_offline)
        layout.addWidget(self._offline_btn)

        # Spacer pushes everything up
        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        return panel

    def _build_plot_area(self) -> QStackedWidget:
        """Build the stacked widget that holds both VisPy plot widgets."""
        self._plot_stack = QStackedWidget()

        self._single_plot = SingleChannelPlotWidget(
            visible_duration_seconds=10.0,
            y_scale=DEFAULT_Y_SCALE,
        )
        self._all_plot = AllChannelsPlotWidget(
            visible_duration_seconds=10.0,
            y_scale=DEFAULT_Y_SCALE,
        )

        self._plot_stack.addWidget(self._single_plot)   # index 0
        self._plot_stack.addWidget(self._all_plot)       # index 1

        return self._plot_stack

    # ================================================================ helpers

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-weight: bold; font-size: 12px;")
        return label

    @staticmethod
    def _divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    # ============================================================ UI handlers

    def _on_connect_clicked(self) -> None:
        """Validate the port input and ask the ViewModel to connect."""
        port_text = self._port_input.text().strip()
        try:
            port = int(port_text)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            self._status_label.setText(
                f"Invalid port: '{port_text}'. Enter a number between 1 and 65535."
            )
            return

        self._vm.connect(port)

    def _on_disconnect_clicked(self) -> None:
        self._vm.disconnect()

    def _on_channel_changed(self, index: int) -> None:
        self._vm.set_channel(index)

    def _on_mode_changed(self, _index: int) -> None:
        self._vm.set_signal_mode(self._mode_combo.currentText())

    def _on_y_scale_changed(self, value: float) -> None:
        self._single_plot.set_y_scale(value)
        self._all_plot.set_y_scale(value)

    def _on_plot_all_channels(self) -> None:
        """Switch to all-channels view and tell the ViewModel to emit all-channel data."""
        self._vm.set_show_all_channels(True)
        self._plot_stack.setCurrentIndex(1)
        self._all_channels_btn.setEnabled(False)
        self._single_ch_btn.setEnabled(True)

    def _on_back_to_single(self) -> None:
        """Switch back to single-channel view."""
        self._vm.set_show_all_channels(False)
        self._plot_stack.setCurrentIndex(0)
        self._all_channels_btn.setEnabled(True)
        self._single_ch_btn.setEnabled(False)

    def _on_open_offline(self) -> None:
        """
        Open the offline Matplotlib inspection window.

        Retrieves the full recording buffer from the ViewModel and passes it
        directly to OfflineInspectionWindow.  Shows an error in the status
        label if no data has been recorded yet.
        """
        result = self._vm.get_offline_data()
        if result is None:
            self._status_label.setText(
                "No recorded data available. Connect to the server and stream some data first."
            )
            return

        full_buffer, sampling_rate = result

        # Create (or recreate) the offline window
        self._offline_window = OfflineInspectionWindow(
            full_buffer=full_buffer,
            sampling_rate=sampling_rate,
            parent=None,   # top-level window
        )
        self._offline_window.show()
        self._offline_window.raise_()

    # ============================================================ VM callbacks

    def _update_time_label(self, signal_time_seconds: float) -> None:
        self._time_label.setText(f"Signal time: {signal_time_seconds:.2f} s")

    def _on_connection_changed(self, connected: bool) -> None:
        """Update button states to reflect the connection state."""
        self._connect_btn.setEnabled(not connected)
        self._disconnect_btn.setEnabled(connected)
        self._port_input.setEnabled(not connected)

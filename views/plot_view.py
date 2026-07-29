"""
VisPy Plot Widget
=================
Provides two live plot widgets:

1. ``SingleChannelPlotWidget``
   Rolling 10-second window for one selected channel.
   - Moving x-axis time labels (like Exercise 5)
   - Visible x-axis and y-axis lines with tick marks
   - Readable y-axis scaling

2. ``AllChannelsPlotWidget``
   Overview of all 32 channels at the same time.
   Each channel is offset vertically so signals do not overlap.
   Example:
       Channel 1   ───── signal
       Channel 2      ───── signal  (shifted up by offset)
       ...
"""

import math
import numpy as np
from PySide6.QtWidgets import QVBoxLayout, QWidget
from vispy import scene


# =========================================================== SingleChannel ===

class SingleChannelPlotWidget(QWidget):
    """
    VisPy widget for real-time single-channel EMG display.

    Mirrors the rolling-window approach from Exercise 5's plotView.py:
    - The visible window is always ``visible_duration_seconds`` wide.
    - Time labels move from right to left as signal time advances.
    - x=0 is always the left edge; newest data appears at the right.
    """

    def __init__(self, visible_duration_seconds: float = 10.0, y_scale: float = 300.0):
        super().__init__()

        self.visible_duration_seconds = visible_duration_seconds
        self.y_scale = y_scale
        self.current_signal_time: float = 0.0
        self.time_tick_step: float = 5.0       # label every 5 s

        # ---- layout ----------------------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- VisPy canvas ----------------------------------------------------
        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=False,
            bgcolor="white",
            size=(1000, 500),
        )

        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "panzoom"

        # Signal line
        self.signal_line = scene.Line(
            pos=np.array([[0.0, 0.0], [1.0, 0.0]], dtype=float),
            color=(0.1, 0.3, 0.8, 1.0),
            parent=self.view.scene,
            width=2,
        )

        # X-axis line (bottom border)
        self.x_axis_line = scene.Line(
            pos=np.array([[0.0, 0.0], [1.0, 0.0]], dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        # Y-axis line (left border)
        self.y_axis_line = scene.Line(
            pos=np.array([[0.0, -1.0], [0.0, 1.0]], dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
        )

        # Tick marks on x-axis (drawn as line segments)
        self.tick_line = scene.Line(
            pos=np.empty((0, 2), dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
            connect="segments",
        )

        # Y-axis tick marks
        self.y_tick_line = scene.Line(
            pos=np.empty((0, 2), dtype=float),
            color=(0.0, 0.0, 0.0, 1.0),
            parent=self.view.scene,
            width=1,
            connect="segments",
        )

        # Floating time labels (up to 8 visible at once)
        self._time_texts = []
        for _ in range(8):
            t = scene.Text(
                text="",
                color="black",
                font_size=9,
                anchor_x="center",
                anchor_y="top",
                parent=self.view.scene,
            )
            self._time_texts.append(t)

        # Y-axis amplitude labels
        self._y_texts = []
        for _ in range(5):
            t = scene.Text(
                text="",
                color="black",
                font_size=9,
                anchor_x="right",
                anchor_y="center",
                parent=self.view.scene,
            )
            self._y_texts.append(t)

        layout.addWidget(self.canvas.native)

        self._update_axes()
        self._update_time_ticks()
        self._update_y_ticks()
        self._update_camera()

    # ---------------------------------------------------------- public API ---

    def set_y_scale(self, y_scale: float) -> None:
        """Update the y-axis range and redraw axes."""
        self.y_scale = float(y_scale)
        self._update_axes()
        self._update_time_ticks()
        self._update_y_ticks()
        self._update_camera()

    def set_signal_time(self, signal_time_seconds: float) -> None:
        """Receive cumulative signal time from the ViewModel and refresh ticks."""
        self.current_signal_time = float(signal_time_seconds)
        self._update_time_ticks()

    def update_plot(self, x: np.ndarray, y: np.ndarray) -> None:
        """
        Redraw the signal line for the current rolling window.

        The x values from the model are 0-based (oldest sample = 0).
        We shift them so the newest sample sits at x = visible_duration_seconds,
        making the signal scroll from right to left.
        """
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        if x.size < 2 or y.size < 2:
            return

        newest_time = x[-1]
        display_x = x - newest_time + self.visible_duration_seconds

        # Only keep points inside the visible window
        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]
        y = y[keep]

        if display_x.size < 2:
            return

        pos = np.column_stack((display_x, y))
        self.signal_line.set_data(pos=pos)
        self._update_camera()

    # ------------------------------------------------------- private helpers --

    def _update_axes(self) -> None:
        y_min = -self.y_scale
        y_max = self.y_scale

        self.x_axis_line.set_data(
            pos=np.array([[0.0, y_min], [self.visible_duration_seconds, y_min]], dtype=float)
        )
        self.y_axis_line.set_data(
            pos=np.array([[0.0, y_min], [0.0, y_max]], dtype=float)
        )

    def _update_time_ticks(self) -> None:
        """Compute and place moving x-axis tick marks and labels."""
        y_min = -self.y_scale
        tick_height = 0.04 * 2 * self.y_scale
        label_y = y_min - 0.06 * 2 * self.y_scale

        visible_start = self.current_signal_time - self.visible_duration_seconds
        visible_end = self.current_signal_time

        first_tick = math.floor(visible_start / self.time_tick_step) * self.time_tick_step
        tick_values = []
        t = first_tick
        while t <= visible_end + self.time_tick_step:
            display_x = t - visible_start
            if t >= 0.0 and 0.0 <= display_x <= self.visible_duration_seconds:
                tick_values.append((t, display_x))
            t += self.time_tick_step

        # Build tick-line segments
        tick_positions = []
        for _, dx in tick_values:
            tick_positions.append([dx, y_min])
            tick_positions.append([dx, y_min + tick_height])

        if tick_positions:
            self.tick_line.set_data(pos=np.asarray(tick_positions, dtype=float))
        else:
            self.tick_line.set_data(pos=np.empty((0, 2), dtype=float))

        # Update floating text labels
        for i, text_obj in enumerate(self._time_texts):
            if i < len(tick_values):
                tick_time, dx = tick_values[i]
                text_obj.text = f"{tick_time:.0f} s"
                text_obj.pos = (dx, label_y)
                text_obj.visible = True
            else:
                text_obj.visible = False

    def _update_y_ticks(self) -> None:
        """Draw 5 evenly-spaced y-axis tick marks with amplitude labels."""
        tick_values = np.linspace(-self.y_scale, self.y_scale, 5)
        tick_width = 0.015 * self.visible_duration_seconds
        tick_positions = []

        for val in tick_values:
            tick_positions.append([0.0, val])
            tick_positions.append([-tick_width, val])

        if tick_positions:
            self.y_tick_line.set_data(pos=np.asarray(tick_positions, dtype=float))

        label_x = -tick_width * 2.5
        for i, text_obj in enumerate(self._y_texts):
            if i < len(tick_values):
                text_obj.text = f"{tick_values[i]:.0f}"
                text_obj.pos = (label_x, float(tick_values[i]))
                text_obj.visible = True
            else:
                text_obj.visible = False

    def _update_camera(self) -> None:
        label_space = 0.16 * 2 * self.y_scale
        self.view.camera.set_range(
            x=(0.0, self.visible_duration_seconds),
            y=(-self.y_scale - label_space, self.y_scale),
            margin=0.02,
        )


# ============================================================ AllChannels ====

class AllChannelsPlotWidget(QWidget):
    """
    VisPy widget that plots all 32 channels simultaneously.

    Each channel is drawn as a separate line with a fixed vertical offset so
    signals can be read without overlapping.

    Layout (bottom → top):
        Channel 0  at  offset * 0
        Channel 1  at  offset * 1
        ...
        Channel 31 at  offset * 31

    A y-axis label identifies each channel on the left side.
    """

    NUM_CHANNELS = 32
    CHANNEL_OFFSET_FACTOR = 2.5    # multiples of y_scale between channels

    def __init__(self, visible_duration_seconds: float = 10.0, y_scale: float = 300.0):
        super().__init__()

        self.visible_duration_seconds = visible_duration_seconds
        self.y_scale = y_scale

        # ---- layout ----------------------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- VisPy canvas ----------------------------------------------------
        self.canvas = scene.SceneCanvas(
            keys="interactive",
            show=False,
            bgcolor="white",
            size=(1000, 800),
        )
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = "panzoom"

        # One Line visual per channel
        self._lines = []
        for ch in range(self.NUM_CHANNELS):
            line = scene.Line(
                pos=np.array([[0.0, 0.0], [1.0, 0.0]], dtype=float),
                color=self._channel_color(ch),
                parent=self.view.scene,
                width=1,
            )
            self._lines.append(line)

        # Channel label per line
        self._labels = []
        for ch in range(self.NUM_CHANNELS):
            t = scene.Text(
                text=f"Ch{ch + 1}",
                color="black",
                font_size=8,
                anchor_x="right",
                anchor_y="center",
                parent=self.view.scene,
            )
            self._labels.append(t)

        # X-axis baseline
        total_height = self.NUM_CHANNELS * self.y_scale * self.CHANNEL_OFFSET_FACTOR
        self.x_axis_line = scene.Line(
            pos=np.array([[0.0, 0.0], [visible_duration_seconds, 0.0]], dtype=float),
            color=(0.0, 0.0, 0.0, 0.6),
            parent=self.view.scene,
            width=1,
        )

        layout.addWidget(self.canvas.native)
        self._update_labels()
        self._update_camera()

    # ---------------------------------------------------------- public API ---

    def set_y_scale(self, y_scale: float) -> None:
        self.y_scale = float(y_scale)
        self._update_labels()
        self._update_camera()

    def update_all_channels(self, x: np.ndarray, data: np.ndarray) -> None:
        """
        Redraw all channel lines.

        Parameters
        ----------
        x    : np.ndarray  shape (N,)   — time axis (0-based, seconds)
        data : np.ndarray  shape (C, N) — processed signal for each channel
        """
        x = np.asarray(x, dtype=float)
        data = np.asarray(data, dtype=float)

        if x.size < 2 or data.shape[1] < 2:
            return

        newest_time = x[-1]
        display_x = x - newest_time + self.visible_duration_seconds
        keep = (display_x >= 0.0) & (display_x <= self.visible_duration_seconds)
        display_x = display_x[keep]

        num_ch = min(data.shape[0], self.NUM_CHANNELS)
        offset_step = self.y_scale * self.CHANNEL_OFFSET_FACTOR

        for ch in range(num_ch):
            y = data[ch, keep]
            offset = ch * offset_step
            y_offset = y + offset

            pos = np.column_stack((display_x, y_offset))
            self._lines[ch].set_data(pos=pos)

        self._update_camera()

    # ------------------------------------------------------- private helpers --

    @staticmethod
    def _channel_color(ch: int):
        """Cycle through a set of distinct colours for readability."""
        palette = [
            (0.1, 0.3, 0.8, 1.0),   # blue
            (0.8, 0.1, 0.1, 1.0),   # red
            (0.1, 0.6, 0.1, 1.0),   # green
            (0.6, 0.1, 0.6, 1.0),   # purple
            (0.8, 0.5, 0.0, 1.0),   # orange
            (0.0, 0.5, 0.5, 1.0),   # teal
            (0.5, 0.3, 0.1, 1.0),   # brown
            (0.3, 0.3, 0.3, 1.0),   # grey
        ]
        return palette[ch % len(palette)]

    def _update_labels(self) -> None:
        offset_step = self.y_scale * self.CHANNEL_OFFSET_FACTOR
        label_x = -0.3   # just left of the y-axis
        for ch, text_obj in enumerate(self._labels):
            offset = ch * offset_step
            text_obj.pos = (label_x, offset)
            text_obj.visible = True

    def _update_camera(self) -> None:
        offset_step = self.y_scale * self.CHANNEL_OFFSET_FACTOR
        total_height = (self.NUM_CHANNELS - 1) * offset_step

        self.view.camera.set_range(
            x=(-0.5, self.visible_duration_seconds),
            y=(-self.y_scale, total_height + self.y_scale),
            margin=0.02,
        )

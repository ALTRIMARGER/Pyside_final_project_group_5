# Final Project — TCP Signal Visualization Application

## Group Information

- **Course:** Applied Programming 2026
- **Team members:** *(fill in your names and student IDs)*
- **Responsibilities:**
  - **Team Member 1 — TCP/Backend (Model):** `models/tcp_client_model.py`, `models/signal_processor.py`
  - **Team Member 2 — Live Visualization & UI (View):** `views/main_view.py`, `views/plot_view.py`
  - **Team Member 3 — Offline Inspection, ViewModel & Integration:** `views/offline_view.py`, `viewmodels/main_view_model.py`, `main.py`

---

## Overview

A PySide6 desktop application for live visualization and offline inspection of
streamed EMG signal data.  The app connects to the provided TCP server
(Exercise 5), receives 32-channel float64 data in real time, and displays it
using VisPy.  After streaming stops the full recorded signal can be inspected
offline with Matplotlib.

---

## Project Structure (MVVM)

```
final_project/
├── main.py                          ← entry point
├── requirements.txt
├── README.md
├── models/
│   ├── tcp_client_model.py          ← TCP connection, byte buffering, rolling + full buffers
│   └── signal_processor.py          ← RMS, bandpass filter (pure functions, no GUI)
├── viewmodels/
│   └── main_view_model.py           ← application state, QTimer polling, Qt signals
└── views/
    ├── main_view.py                 ← main window, all controls
    ├── plot_view.py                 ← VisPy live widgets (single-channel + all-channels)
    └── offline_view.py              ← Matplotlib offline inspection window
```

| Layer      | Responsibility |
|------------|----------------|
| **Model**  | TCP socket, byte buffering, packet reconstruction, rolling/full buffers, signal processing |
| **ViewModel** | Owns the model, drives a QTimer, applies signal processing, emits Qt signals to the View |
| **View**   | GUI widgets only; receives data exclusively through ViewModel signals |

The View never receives TCP data directly.  The Model contains no GUI code.

---

## Installation

### Option A — pip

```bash
pip install -r requirements.txt
```

### Option B — uv (recommended, matches course setup)

```bash
uv sync
```

Dependencies: `numpy`, `scipy`, `PySide6`, `vispy`, `matplotlib`

---

## Running the Application

### 1. Start the TCP server

The server is located in `TCP_Server/main.py` at the repository root.
Open a terminal and run:

```bash
# from the repository root
python TCP_Server/main.py
```

The server starts on `localhost:12345` by default.

### 2. Start the application

```bash
# from the final_project directory
python main.py

# or from the repository root with uv
uv run final_project/main.py
```

---

## How to Use

### Connecting to the TCP Server

1. Enter the TCP port in the **Port** field (default: `12345`).
2. Click **Connect**.
3. The status label shows `Connected to localhost:XXXX. Streaming…` on success,
   or an error message if the server is not running or the port is wrong.
4. Streaming starts automatically after a successful connection.
5. Click **Disconnect** to stop streaming at any time.

### Live Plot — Single Channel

- Use the **Channel** dropdown to select any of the 32 channels (Ch 1 – Ch 32).
- Use the **Signal mode** dropdown to switch between:
  - **Original** — raw signal as received
  - **RMS** — RMS envelope (100 ms sliding window)
  - **Filtered** — bandpass-filtered signal (20–450 Hz)
- Adjust **Y-scale (±)** to zoom the amplitude axis in or out.
- The rolling window always shows the last **10 seconds** of data.
- The x-axis carries moving time labels (seconds) that scroll left as new data arrives.

### Live Plot — All Channels

- Click **Plot All Channels** to switch to an overview of all 32 channels at once.
- Each channel is drawn with a fixed vertical offset so signals do not overlap:
  ```
  Channel 1   ───── signal
  Channel 2      ───── signal
  ...
  Channel 32                  ───── signal
  ```
- The same signal mode and y-scale settings apply.
- Click **Back to Single Channel** to return to the single-channel view.

### Offline Inspection (Matplotlib)

1. Stream some data (or disconnect after streaming).
2. Click **Open Offline Plot**.
3. A separate Matplotlib window opens with the full recorded signal.
4. Use the **Channel** and **Signal mode** dropdowns to inspect any channel in
   any mode; the plot updates immediately.
5. The window shows total recording duration and number of samples.

---

## Team Member 2 — Live Visualization & UI

**Files owned:** `views/main_view.py`, `views/plot_view.py`

### What was implemented

#### 1. GUI Layout — `views/main_view.py`

`MainView` is the top-level `QMainWindow`. The window is split into two areas:

- **Left control panel** (240 px fixed width) contains, top to bottom:
  - *TCP Connection* section — port `QLineEdit`, **Connect** and **Disconnect** buttons, a status `QLabel` that receives text from the ViewModel
  - *Signal time* label — updates live in bold (e.g. `Signal time: 12.34 s`)
  - *Live Plot Settings* section — channel `QComboBox` (Ch 1–32), signal mode `QComboBox` (Original / RMS / Filtered), Y-scale `QDoubleSpinBox`
  - **Plot All Channels** and **Back to Single Channel** toggle buttons
  - *Offline Inspection* section — **Open Offline Plot** button

- **Right plot area** — a `QStackedWidget` that swaps between `SingleChannelPlotWidget` (index 0) and `AllChannelsPlotWidget` (index 1) without tearing down either widget.

The View connects to the ViewModel purely through Qt signals and method calls — it never accesses the TCP model or the data buffers directly:

| ViewModel signal | View action |
|-----------------|-------------|
| `plot_updated(x, y)` | `SingleChannelPlotWidget.update_plot()` |
| `all_channels_updated(x, data)` | `AllChannelsPlotWidget.update_all_channels()` |
| `status_updated(str)` | status label text |
| `signal_time_updated(float)` | time label + `set_signal_time()` on single-channel widget |
| `connection_changed(bool)` | enable/disable Connect, Disconnect, port input |

#### 2. Single-Channel Live Plot — `SingleChannelPlotWidget`

Built with `vispy.scene`. Key design decisions:

- **Scrolling window:** x values from the model are 0-based. They are shifted so the newest sample always lands at `x = visible_duration_seconds` (10 s), making the signal scroll right-to-left naturally.
- **Axes:** drawn as manual `scene.Line` objects (x-axis at `y = -y_scale`, y-axis at `x = 0`) so they are always visible regardless of zoom.
- **Moving time labels:** up to 8 `scene.Text` objects are repositioned every frame at every 5 s tick mark. Labels only appear for non-negative signal times, matching the Exercise 5 approach.
- **Y-axis labels:** 5 evenly-spaced amplitude tick marks with values displayed to the left of the y-axis line.
- **Y-scale control:** `set_y_scale(value)` redraws all axes and resets the camera — called directly by the Y-scale spinbox.

#### 3. All-Channels Overview — `AllChannelsPlotWidget`

- Creates **32 individual `scene.Line` objects**, one per channel, using a cycling 8-colour palette (blue, red, green, purple, orange, teal, brown, grey).
- Each channel `ch` is shifted vertically by `ch × y_scale × 2.5` so signals are spaced clearly without overlapping.
- A `scene.Text` label (`Ch1` … `Ch32`) sits to the left of each channel's baseline.
- `update_all_channels(x, data)` applies the same right-to-left clipping logic as the single-channel widget, then updates all 32 lines in one loop.
- The camera covers the full vertical extent of all 32 channels automatically.

### How it connects to the other teammates' work

```
Model (Team Member 1)
    ↓  get_window() / get_all_channels_window()
ViewModel (Team Member 3)
    ↓  plot_updated  /  all_channels_updated  (Qt signals)
View (Team Member 2)  ← YOU ARE HERE
    ↓  SingleChannelPlotWidget.update_plot()
    ↓  AllChannelsPlotWidget.update_all_channels()
```

The View expects these exact signal signatures from the ViewModel:

```python
plot_updated         = Signal(object, object)   # (x: np.ndarray, y: np.ndarray)
all_channels_updated = Signal(object, object)   # (x: np.ndarray, data: np.ndarray[32, N])
status_updated       = Signal(str)
signal_time_updated  = Signal(float)
connection_changed   = Signal(bool)
```

And calls these ViewModel methods in response to user actions:

```python
vm.connect(port: int)
vm.disconnect()
vm.set_channel(index: int)
vm.set_signal_mode(mode: str)   # "Original" | "RMS" | "Filtered"
vm.set_show_all_channels(enabled: bool)
vm.get_offline_data()           # returns (full_buffer, sampling_rate) or None
```

---

| Parameter | Value |
|-----------|-------|
| RMS window | **100 ms** sliding window, implemented with `np.convolve(..., mode="same")` |
| Filter type | **4th-order Butterworth bandpass**, zero-phase (`scipy.signal.filtfilt`) |
| Low cutoff | **20 Hz** |
| High cutoff | **450 Hz** |

These values match the standard EMG processing parameters used in the course
exercises (Exercise 2 and Exercise 3).

---

## TCP Data Format

Matches the server provided in Exercise 5:

| Property | Value |
|----------|-------|
| Channels | 32 |
| Samples per packet | 18 |
| Data type | `float64` |
| Bytes per packet | 32 × 18 × 8 = **4608 bytes** |
| Sampling rate | 2000 Hz |

The client accumulates raw bytes in a `bytearray`, extracts complete 4608-byte
packets, and deserialises them with `np.frombuffer`.

---

## Error Handling

| Situation | Behaviour |
|-----------|-----------|
| Server not running | Status label: `Could not connect: …` |
| Invalid port entered | Status label: `Invalid port: '…'` |
| Server closes connection | Timer stops; status: `Server closed the connection.` |
| No data for offline plot | Status label explains that streaming must happen first |
| Signal too short to filter | Raw signal returned instead of crashing |
| Unknown signal mode | `ValueError` caught; raw signal used as fallback |

---

## Submission

Send the GitHub repository link to:

- Daniel Fenzel: daniel.fenzel@fau.de
- Annika Ritter: annika.ritter@fau.de

Deadline: **31.07., 24:00**

"""
TCP Client Model
================
Handles the TCP connection to the EMG server, byte-level packet reconstruction,
a rolling live buffer (10 s), and a full recording buffer for offline inspection.

Server data format:
    - 32 channels
    - 18 samples per packet
    - float64 values
    - sent as raw bytes via current_window.tobytes(order="C")

One packet:  32 * 18 * 8 = 4608 bytes
"""

import socket
import numpy as np


class TcpClientModel:
    """
    Manages the TCP connection and all data buffering.

    Attributes
    ----------
    data_buffer : np.ndarray  (channels, N)
        Rolling live buffer — keeps the most recent ``window_seconds`` of data.
    full_buffer : np.ndarray  (channels, N)
        Full recording buffer — grows for the entire session; used for offline
        Matplotlib inspection after streaming stops.
    total_samples_received : int
        Cumulative sample count; used to compute the signal time axis.
    """

    # ------------------------------------------------------------------ init --

    def __init__(
        self,
        host: str = "localhost",
        port: int = 12345,
        sampling_rate: float = 2000.0,
        channels: int = 32,
        samples_per_packet: int = 18,
        window_seconds: float = 10.0,
        selected_channel: int = 0,
    ):
        self.host = host
        self.port = port
        self.sampling_rate = sampling_rate
        self.channels = channels
        self.samples_per_packet = samples_per_packet
        self.window_seconds = window_seconds
        self.selected_channel = selected_channel

        # Data type must match the server (.tobytes() is called on float64 array)
        self.dtype = np.float64

        self.socket: socket.socket | None = None
        self.is_connected: bool = False

        # Pre-compute sizes
        self.packet_size: int = channels * samples_per_packet
        self.packet_size_bytes: int = self.packet_size * np.dtype(self.dtype).itemsize
        self.window_size: int = int(sampling_rate * window_seconds)

        # Byte-level accumulation buffer for partial TCP reads
        self.byte_buffer = bytearray()

        # Rolling 10 s buffer for live VisPy plot
        self.data_buffer = np.empty((channels, 0), dtype=self.dtype)

        # Full buffer for offline Matplotlib inspection
        self.full_buffer = np.empty((channels, 0), dtype=self.dtype)

        self.total_samples_received: int = 0

    # --------------------------------------------------------------- connect --

    def connect(self) -> None:
        """
        Open a TCP connection to the EMG server.

        Raises
        ------
        OSError
            If the server is not reachable or the port is wrong.
        """
        if self.is_connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

        # Non-blocking so that recv() does not freeze the Qt event loop.
        self.socket.setblocking(False)

        self.is_connected = True

    # ------------------------------------------------------------ disconnect --

    def disconnect(self) -> None:
        """Close the TCP connection and release the socket."""
        self.is_connected = False

        if self.socket is not None:
            self.socket.close()
            self.socket = None

    # --------------------------------------------------------- receive_data --

    def receive_data(self) -> None:
        """
        Pull all currently available bytes from the TCP socket.

        TCP is a byte stream — one recv() call does not necessarily align with
        one packet boundary.  We therefore:
          1. Accumulate raw bytes into ``self.byte_buffer``.
          2. Extract complete 4608-byte packets in ``_extract_packets_from_buffer``.
        """
        if not self.is_connected or self.socket is None:
            return

        while True:
            try:
                new_bytes = self.socket.recv(4096)

                if not new_bytes:
                    # Server closed the connection gracefully.
                    self.disconnect()
                    return

                self.byte_buffer.extend(new_bytes)

            except BlockingIOError:
                # No more bytes available right now — stop reading.
                break
            except OSError:
                # Socket was closed from the other end unexpectedly.
                self.disconnect()
                return

        self._extract_packets_from_buffer()

    # ----------------------------------------- _extract_packets_from_buffer --

    def _extract_packets_from_buffer(self) -> None:
        """
        Convert all complete packets in the byte buffer into NumPy arrays and
        append them to both the rolling live buffer and the full recording buffer.

        One complete packet:
            channels * samples_per_packet = 32 * 18 = 576 float64 values
            576 * 8 bytes = 4608 bytes
        """
        packets = []

        while len(self.byte_buffer) >= self.packet_size_bytes:
            # Slice one complete packet from the front of the byte buffer.
            packet_bytes = self.byte_buffer[: self.packet_size_bytes]
            del self.byte_buffer[: self.packet_size_bytes]

            # Deserialise bytes → NumPy array → reshape to (channels, samples)
            packet = np.frombuffer(packet_bytes, dtype=self.dtype)
            packet = packet.reshape(self.channels, self.samples_per_packet)

            packets.append(packet)

        if not packets:
            return

        # Concatenate all new packets into one block: (channels, new_samples)
        new_data = np.concatenate(packets, axis=1)

        # --- Rolling live buffer -------------------------------------------
        self.data_buffer = np.concatenate((self.data_buffer, new_data), axis=1)
        self.total_samples_received += new_data.shape[1]

        # Trim to the most recent window_size samples
        if self.data_buffer.shape[1] > self.window_size:
            self.data_buffer = self.data_buffer[:, -self.window_size :]

        # --- Full recording buffer (for offline inspection) -----------------
        self.full_buffer = np.concatenate((self.full_buffer, new_data), axis=1)

    # ------------------------------------------------------------- has_data --

    def has_data(self) -> bool:
        """Return True if the live buffer has at least two samples to plot."""
        return self.data_buffer.shape[1] >= 2

    def has_full_data(self) -> bool:
        """Return True if the full recording buffer has data for offline view."""
        return self.full_buffer.shape[1] >= 2

    # ------------------------------------------------------------- get_window --

    def get_window(self):
        """
        Return the current rolling window as (x, y) arrays.

        x : relative time axis in seconds (0 … window_seconds)
        y : signal values for ``selected_channel``
        """
        y = self.data_buffer[self.selected_channel, :]
        n = y.shape[0]
        x = np.arange(n) / self.sampling_rate
        return x, y

    def get_all_channels_window(self):
        """
        Return the current rolling window for all channels.

        Returns
        -------
        x : np.ndarray  shape (N,)
        data : np.ndarray  shape (channels, N)
        """
        data = self.data_buffer
        n = data.shape[1]
        x = np.arange(n) / self.sampling_rate
        return x, data

    # ------------------------------------------------------- signal time ------

    def get_signal_time_seconds(self) -> float:
        """
        Return the cumulative signal time in seconds.

            signal_time = total_samples_received / sampling_rate
        """
        return self.total_samples_received / self.sampling_rate

    # ----------------------------------------------------------- reset --------

    def reset_buffers(self) -> None:
        """Clear all buffers — call before starting a new recording session."""
        self.byte_buffer = bytearray()
        self.data_buffer = np.empty((self.channels, 0), dtype=self.dtype)
        self.full_buffer = np.empty((self.channels, 0), dtype=self.dtype)
        self.total_samples_received = 0

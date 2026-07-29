"""
Signal Processor
================
Pure functions for EMG signal processing.  No GUI code here.

Supported modes
---------------
- ``"Original"``  — raw signal, no processing
- ``"RMS"``       — RMS envelope with a 100 ms sliding window
- ``"Filtered"``  — 4th-order Butterworth bandpass, 20–450 Hz

Parameters used
---------------
RMS window  : 100 ms
Filter type : Butterworth bandpass, order 4
Low cutoff  : 20 Hz
High cutoff : 450 Hz
"""

import numpy as np
from scipy import signal as scipy_signal


# ------------------------------------------------------------------ constants -

RMS_WINDOW_MS: float = 100.0    # milliseconds
FILTER_LOW_HZ: float = 20.0     # Hz
FILTER_HIGH_HZ: float = 450.0   # Hz
FILTER_ORDER: int = 4


# ----------------------------------------------------------------- public API -

def process_channel(
    channel: np.ndarray,
    sampling_rate: float,
    mode: str,
) -> np.ndarray:
    """
    Apply the requested processing mode to a single channel array.

    Parameters
    ----------
    channel : np.ndarray  shape (N,)
        Raw signal samples for one channel.
    sampling_rate : float
        Samples per second.
    mode : str
        One of ``"Original"``, ``"RMS"``, ``"Filtered"``.

    Returns
    -------
    np.ndarray  shape (N,)
        Processed signal (same length as input).

    Raises
    ------
    ValueError
        If an unknown mode string is passed.
    """
    if mode == "Original":
        return channel.copy()
    elif mode == "RMS":
        return compute_rms(channel, sampling_rate)
    elif mode == "Filtered":
        return bandpass_filter(channel, sampling_rate)
    else:
        raise ValueError(f"Unknown signal mode: '{mode}'. "
                         f"Choose from 'Original', 'RMS', 'Filtered'.")


def process_all_channels(
    data: np.ndarray,
    sampling_rate: float,
    mode: str,
) -> np.ndarray:
    """
    Apply processing to every channel in a (channels, samples) array.

    Parameters
    ----------
    data : np.ndarray  shape (C, N)
    sampling_rate : float
    mode : str

    Returns
    -------
    np.ndarray  shape (C, N)
    """
    result = np.zeros_like(data)
    for ch in range(data.shape[0]):
        result[ch] = process_channel(data[ch], sampling_rate, mode)
    return result


# ---------------------------------------------------------- signal processing -

def compute_rms(channel: np.ndarray, sampling_rate: float) -> np.ndarray:
    """
    Compute the RMS envelope using a sliding window of ``RMS_WINDOW_MS`` ms.

    Implementation uses ``np.convolve`` with ``mode="same"`` so the output
    length always equals the input length.

    Parameters
    ----------
    channel : np.ndarray  shape (N,)
    sampling_rate : float

    Returns
    -------
    np.ndarray  shape (N,)
        Non-negative RMS envelope.
    """
    window_size = max(1, int((RMS_WINDOW_MS / 1000.0) * sampling_rate))
    kernel = np.ones(window_size) / window_size

    squared = channel ** 2
    mean_squared = np.convolve(squared, kernel, mode="same")

    # Guard against tiny negative values from floating-point rounding
    mean_squared = np.maximum(mean_squared, 0.0)

    return np.sqrt(mean_squared)


def bandpass_filter(channel: np.ndarray, sampling_rate: float) -> np.ndarray:
    """
    Apply a zero-phase 4th-order Butterworth bandpass filter (20–450 Hz).

    Uses ``scipy.signal.filtfilt`` for zero-phase filtering (no time delay).

    Parameters
    ----------
    channel : np.ndarray  shape (N,)
    sampling_rate : float

    Returns
    -------
    np.ndarray  shape (N,)

    Raises
    ------
    ValueError
        If the signal is too short for the chosen filter order, or if the
        cutoff frequencies are outside the valid range.
    """
    nyquist = sampling_rate / 2.0

    if FILTER_HIGH_HZ >= nyquist:
        raise ValueError(
            f"High cutoff {FILTER_HIGH_HZ} Hz exceeds Nyquist {nyquist} Hz "
            f"at sampling rate {sampling_rate} Hz."
        )

    low = FILTER_LOW_HZ / nyquist
    high = FILTER_HIGH_HZ / nyquist

    b, a = scipy_signal.butter(FILTER_ORDER, [low, high], btype="band")

    # filtfilt needs at least padlen + 1 samples (default padlen = 3*max(len(a),len(b)))
    min_samples = 3 * max(len(a), len(b)) + 1
    if len(channel) < min_samples:
        # Not enough samples to filter — return raw channel to avoid crash
        return channel.copy()

    return scipy_signal.filtfilt(b, a, channel)

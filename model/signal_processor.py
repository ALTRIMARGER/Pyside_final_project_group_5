import numpy as np
from scipy import signal


class SignalProcessor:

    def __init__(self):
        pass

    def original(self, data):
        return data

    def filtered(self, data, sampling_rate, low_cut=20, high_cut=450):

        nyquist = sampling_rate / 2

        low = low_cut / nyquist
        high = high_cut / nyquist

        b, a = signal.butter(4, [low, high], btype="band")

        filtered = np.zeros_like(data)

        for i in range(data.shape[0]):
            filtered[i, :] = signal.filtfilt(b, a, data[i, :])

        return filtered

    def rms(self, data, sampling_rate, window_ms=100):

        window_size = int((window_ms / 1000) * sampling_rate)
        half_window = window_size // 2

        rms_signal = np.zeros_like(data)

        for channel in range(data.shape[0]):

            signal_data = data[channel, :]

            for i in range(signal_data.shape[0]):

                start = max(0, i - half_window)
                end = min(signal_data.shape[0], i + half_window)

                window = signal_data[start:end]

                rms_signal[channel, i] = np.sqrt(np.mean(window ** 2))

        return rms_signal


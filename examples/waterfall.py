"""
Frequency waterfall class method using a PicoScope.
This method uses an advanced block capture loop to retrieve data from the
PicoScope.

Setup:
 - Connect SigGen output to Channel A
"""
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import windows
from matplotlib import pyplot as plt
from matplotlib import animation
from pypicosdk import psospa, CHANNEL, RANGE, WAVEFORM, SAMPLE_RATE, SWEEP_TYPE

# Capture config
SAMPLES = 5_000
RATE = 500
unit = SAMPLE_RATE.MSPS

channel = CHANNEL.A
ch_range = RANGE.V1
TIME_UNIT = 's'

# SigGen config
START_FREQ = 1E6
STOP_FREQ = 20E6
STEP = 2.5E3
SWEEP = SWEEP_TYPE.UPDOWN
PK2PK = 1.0
waveform = WAVEFORM.SQUARE

# Waterfall config
WATERFALL_LINES = 100
MIN_DB = -100
MAX_DB = 0


class Waterfall:
    "Waterfall class"
    def __init__(self, scope_class):
        self.scope: psospa = scope_class
        self.window = windows.hann(SAMPLES)
        self.waterfall = np.full((WATERFALL_LINES, SAMPLES // 2 + 1), MIN_DB)  # waterfall storage
        self.fft_dbs: np.ndarray
        self.buffer_volts: np.ndarray

        self.setup_scope()
        self.setup_siggen()
        self.setup_animation()
        self.scope_loop()

    def setup_scope(self):
        "Setup the oscilloscope"
        # Setup channel A and retrieve interval information
        self.scope.open_unit()
        self.scope.set_channel(channel, ch_range)
        self.scope.set_simple_trigger(channel, threshold_mv=0)
        self.timebase = self.scope.sample_rate_to_timebase(RATE, unit)
        self.time_axis = self.scope.get_time_axis(self.timebase, SAMPLES, TIME_UNIT)
        self.actual_interval = self.time_axis[1] - self.time_axis[0]

        # Create buffer to store capture (Advanced Block)
        self.buffer = self.scope.set_data_buffer(channel, SAMPLES)

        # Retrieve fft minimum and maximum values
        fft_freqs = rfftfreq(SAMPLES, self.actual_interval) / 1e6
        self.fft_min, self.fft_max = fft_freqs[0], fft_freqs[-1]

    def setup_siggen(self):
        "Setup SigGen"
        self.scope.set_siggen(START_FREQ, PK2PK, waveform, sweep=True,
                              stop_freq=STOP_FREQ, inc_freq=STEP, sweep_type=SWEEP)

    def setup_animation(self):
        "Setup pyplot imshow animation"
        self.fig, ax = plt.subplots()
        self.image = ax.imshow(self.waterfall, aspect='auto', origin='lower',
                               extent=[self.fft_min, self.fft_max, 0, WATERFALL_LINES],
                               cmap='viridis', vmin=MIN_DB, vmax=MAX_DB)
        ax.set_xlabel("Frequency (MHz)")
        ax.set_ylabel("Time Step")
        ax.set_title("Real-Time Spectrum Waterfall")

    def run_block_fft(self):
        "Run block capture, retrieve data and convert to Volts (V)"
        self.scope.run_block_capture(self.timebase, SAMPLES)
        self.scope.get_values(SAMPLES)
        self.buffer_volts = self.scope.adc_to_volts(self.buffer, channel)

    def build_fft(self):
        "Build FFT and append to waterfall 2d array"
        # Filter data using Hann window
        buf_windowed = self.buffer_volts * self.window

        # Generate FFT on windowed data (compensating for window)
        amplitudes = np.abs(rfft(buf_windowed)) / np.sum(self.window)
        self.fft_dbs = 20 * np.log10(amplitudes)

        # Scroll waterfall and add new FFT buffer
        self.waterfall = np.roll(self.waterfall, -1, axis=0)
        self.waterfall[-1, :] = self.fft_dbs

    def scope_loop(self):
        "Main PicoScope loop - add in here to change freq of SigGen"
        self.run_block_fft()
        self.build_fft()

    def update(self, _frame):
        "Update waterfall graph animation"
        self.scope_loop()

        # Add waterfall data to image
        self.image.set_array(self.waterfall)
        return [self.image]


if __name__ == '__main__':
    # Setup scope and waterfall class
    scope = psospa()
    waterfall = Waterfall(scope)

    # Setup waterfall animation
    _ = animation.FuncAnimation(waterfall.fig, waterfall.update, frames=100,
                                interval=100, blit=False)
    plt.show()

    scope.close_unit()

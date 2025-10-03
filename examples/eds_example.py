"""
Frequency waterfall class method using a PicoScope.
This method uses an advanced block capture loop to retrieve data from the
PicoScope.

Setup:
 - Connect SigGen output to Channel A
"""
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button
import measurement_examples.measurements as meas
from pypicosdk import psospa, CHANNEL, RANGE, WAVEFORM, SAMPLE_RATE

# Capture config
SAMPLES = 5_000
RATE = 1
unit = SAMPLE_RATE.MSPS

channel = CHANNEL.A
ch_range = RANGE.V1
OUTPUT_UNIT = 'mV'
TIME_UNIT = 'us'
THRESHOLD = 0
AUTO_TRIGGER_MS = 500
AUTO_TRIGGER_US = int(AUTO_TRIGGER_MS * 1e3)

# SigGen config
FREQ = 1E3
PK2PK = 1.6
waveform = WAVEFORM.SQUARE

# Waterfall config
WATERFALL_LINES = 100
MIN_DB = -100
MAX_DB = 0


class ScopeAnimation:
    "Waterfall class"
    def __init__(self, scope_class):
        self.scope: psospa = scope_class
        self.line: np.ndarray
        self.buffer_volts: np.ndarray

        self.freq: float = FREQ

        self.setup_scope()
        self.run_block()
        self.setup_animation()

    def setup_scope(self):
        "Setup the oscilloscope"
        # Setup channel A and retrieve interval information
        self.scope.open_unit()
        self.scope.set_channel(channel, ch_range)
        self.scope.set_simple_trigger(channel, threshold_mv=0, auto_trigger=AUTO_TRIGGER_US)
        self.timebase = self.scope.sample_rate_to_timebase(RATE, unit)
        self.time_axis = self.scope.get_time_axis(self.timebase, SAMPLES, unit=TIME_UNIT,
                                                  pre_trig_percent=50)
        self.actual_interval = self.time_axis[1] - self.time_axis[0]
        self.scope.set_siggen(FREQ, PK2PK, waveform)

        # Create buffer to store capture (Advanced Block)
        self.buffer = self.scope.set_data_buffer(channel, SAMPLES)

    def button_inc_freq(self, _):
        "Button action to increase siggen freq"
        self.freq += 100
        self.set_siggen_freq(self.freq)

    def button_dec_freq(self, _):
        "Button action to decrease siggen freq"
        self.freq -= 100
        self.set_siggen_freq(self.freq)

    def set_siggen_freq(self, freq):
        "Set siggen freq"
        self.scope.siggen_set_frequency(freq)
        self.scope.siggen_apply()

    def setup_animation(self):
        "Setup pyplot imshow animation"
        self.fig, ax = plt.subplots()
        plt.subplots_adjust(bottom=0.3)
        ax.set_ylabel(f'Amplitude ({OUTPUT_UNIT})')
        ax.set_ylim(self.scope.get_ylim())
        ax.set_xlim(self.time_axis[0], self.time_axis[-1])
        ax.set_xlabel('Time (μs)')
        self.btn_dec_ax = self.fig.add_axes([0.50, 0.05, 0.2, 0.075])
        self.btn_dec = Button(self.btn_dec_ax, 'Dec Freq.')
        self.btn_dec.on_clicked(self.button_dec_freq)

        self.line, = ax.plot(self.time_axis, self.buffer_volts)
        self.btn_inc_ax = self.fig.add_axes([0.75, 0.05, 0.2, 0.075])
        self.btn_inc = Button(self.btn_inc_ax, 'Inc Freq.')
        self.btn_inc.on_clicked(self.button_inc_freq)

    def run_block(self):
        "Run block capture, retrieve data and convert to volts"
        self.scope.run_block_capture(self.timebase, SAMPLES)
        self.scope.get_values(SAMPLES)
        self.buffer_volts = self.scope.adc_to_mv(self.buffer, channel)
        calculated_freq = meas.measure_frequency(
            self.buffer_volts, RATE*1e6, 0.5*self.buffer_volts.max())
        print(f'Calculated frequency: {calculated_freq:.2f}, actual frequency: {self.freq}')

    def update(self, _frame):
        "Update graph animation"
        self.run_block()
        self.line.set_data(self.time_axis, self.buffer_volts)
        return [self.line]


if __name__ == '__main__':
    # Setup scope and waterfall class
    scope = psospa()
    scopeAnimation = ScopeAnimation(scope)

    # Setup waterfall animation
    _ = FuncAnimation(scopeAnimation.fig, scopeAnimation.update, frames=100,
                      interval=50, blit=False)
    plt.show()

    scope.close_unit()

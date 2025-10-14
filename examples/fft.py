"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

FFT example for a PicoScope 6000E.

Description:
  This will convert the voltage data to the frequency domain and
  display it in pyplot, also calculating the peak frequency.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) matplotlib scipy numpy pypicosdk

Setup:
  - Connect 6000E SigGen (AWG) to Channel A of the oscilloscope
    using a BNC cable or probe

"""

from matplotlib import pyplot as plt
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import windows
import pypicosdk as psdk

# Capture configuration
SAMPLES = 5_000_000

# Create "scope" class and initialize PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Set siggen to 10MHz & 800mVpkpk output square wave
scope.set_siggen(frequency=10_000_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SQUARE)

# Enable channel A with +/- 1V range (2V total dynamic range)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure a simple rising edge trigger for channel A, wait indefinitely (do not auto trigger)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold=0, auto_trigger=0)

# Helper function to set timebase of scope via requested sample rate
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)

# Unused alternate methods to set sample rate / interval
# TIMEBASE = 2                                      # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(2E-9)       # set timebase via requested sample interval

# Print to console the actual sample rate selected by the device driver
print(scope.get_actual_sample_rate())

# Create buffers in this application space to hold returned sample array
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Get actual sample interval
actual_interval = scope.get_actual_interval()

# Create a Hanning window and apply to data
window = windows.hann(SAMPLES)
v_windowed = channel_buffer[psdk.CHANNEL.A] * window

# Create fft from windowed data
positive_amplitudes = np.abs(rfft(v_windowed))
positive_freqs = rfftfreq(SAMPLES, actual_interval)

# # Convert mV to dB
positive_dbs = np.abs(20 * np.log10(positive_amplitudes / 1e3))

# Calculate peak frequency and level, and print result to console
peak_index = np.argmax(positive_dbs)
print(f'Peak frequency: {positive_freqs[peak_index]/1e6:.2f} MHz, ' +
      f'{positive_dbs[peak_index]:.2F} dB')

# Use matplotlib to plot the data
plt.figure(figsize=(10, 4))
plt.plot(positive_freqs / 1e6, positive_dbs)
plt.xlim(0, positive_freqs.max()/1e6)
plt.ylim(0)
plt.xlabel("Frequency (MHz)")
plt.ylabel("Amplitude (dB)")
plt.title("FFT of Voltage Signal")
plt.grid(True)
plt.tight_layout()
plt.show()

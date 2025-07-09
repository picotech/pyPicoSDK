##################################################################
# FFT example for a PicoScope 6000E.
#
# Description:
#   This will convert the voltage data to the frequency domain and
#   display it in pyplot, also calculating the peak frequency.
#
# Requirements: 
# - PicoScope 6000E
# - Python packages:
#   pip install matplotlib scipy numpy pypicosdk
#
# Setup:
#   - Connect 6000E SigGen (AWG) to Channel A of the oscilloscope
#     using a BNC cable or probe
#
##################################################################

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Pico examples use inline argument values for clarity
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import windows

# Capture configuration
SAMPLES = 5_000_000
THRESHOLD = 0

# SigGen variables
frequency = 10_000_000
pk2pk = 0.8
wave_type = psdk.WAVEFORM.SQUARE

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency, pk2pk, wave_type)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=THRESHOLD)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 3  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Take out data (converting ns time axis to s)
v = np.array(channel_buffer[psdk.CHANNEL.A])
t = np.array(time_axis) * 1E-9

# Get sample rate
dt = t[1] - t[0]

# Create a window and apply to data
window = windows.hann(SAMPLES)
v_windowed = v * window

# Create fft from data
positive_amplitudes = np.abs(rfft(v_windowed))
positive_freqs = rfftfreq(SAMPLES, dt)

# # Convert mV to dB
positive_dbs = np.abs(20 * np.log10(positive_amplitudes / 1e3))

# # Calculate peak frequency
peak_index = np.argmax(positive_dbs)
print(f'Peak frequency: {positive_freqs[peak_index]/1e6:.2f} MHz, ' +
      f'{positive_dbs[peak_index]:.2F} dB')

# Plot data to pyplot
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

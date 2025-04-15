##################################################################
# FFT example for a PicoScope 6000E.
#
# Description:
#   This will convert the voltage data to the frequency domain and
#   display it in pyplot
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
import numpy as np
from scipy.fft import fft, fftfreq
from scipy.signal import windows

# Setup variables
timebase = 3
samples = 5_000_000
channel_a = psdk.CHANNEL.A
range = psdk.RANGE.V1
threshold = 0

# SigGen variables
frequency = 1_000_000
pk2pk = 0.8
wave_type = psdk.WAVEFORM.SQUARE

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency, pk2pk, wave_type)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=threshold)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(timebase, samples)

# Finish with PicoScope
scope.close_unit()

# Take out data (converting ns time axis to s)
v = np.array(channel_buffer[channel_a])
t = np.array(time_axis) * 1E-9

# Get sample rate
dt = t[1] - t[0]

# Create a window and apply to data
window = windows.hann(samples)
v_windowed = v * window

# Create fft from data
V_f = fft(v_windowed)
freqs = fftfreq(samples, dt)

# Remove negative frequency data
positive_freqs = freqs[:samples//2]
amplitudes = np.abs(V_f[:samples//2])

# Plot data to pyplot
plt.figure(figsize=(10, 4))
plt.plot(positive_freqs / 1e6, amplitudes)  # Convert Hz to MHz
plt.xlabel("Frequency (MHz)")
plt.ylabel("Amplitude (mV)")
plt.title("FFT of Voltage Signal")
plt.grid(True)
plt.tight_layout()
plt.show()

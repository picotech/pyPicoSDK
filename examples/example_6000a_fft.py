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
import numpy as np
from scipy.fft import rfft, rfftfreq
from scipy.signal import windows

# Setup variables
samples = 5_000_000
channel_a = psdk.CHANNEL.A
range = psdk.RANGE.V1
threshold = 0

# SigGen variables
frequency = 10_000_000
pk2pk = 0.8
wave_type = psdk.WAVEFORM.SQUARE

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Set capture timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500,
                                         unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Setup siggen
scope.set_siggen(frequency, pk2pk, wave_type)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=threshold)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(
    TIMEBASE, samples, time_unit=psdk.TIME_UNIT.S
)

# Finish with PicoScope
scope.close_unit()

# Take out data; time axis already in seconds
v = np.array(channel_buffer[channel_a])
t = np.array(time_axis)

# Get sample rate
dt = t[1] - t[0]

# Create a window and apply to data
window = windows.hann(samples)
v_windowed = v * window

# Create fft from data
positive_amplitudes = np.abs(rfft(v_windowed))
positive_freqs = rfftfreq(samples, dt)

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

##################################################################
# FFT example for a PicoScope 6000E.
#
# Description:
#   This example script captures multiple signals and displays
#   a histogram of captured peak-to-peak (pk2pk) values along
#   with similar measurements
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
import matplotlib.pyplot as plt
import numpy as np

# Scope setup
scope = psdk.ps6000a()
scope.open_unit(resolution=psdk.RESOLUTION._12BIT)

# Set channels
channel = psdk.CHANNEL.A

scope.set_channel(channel=psdk.CHANNEL.A, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)
scope.set_channel(channel=psdk.CHANNEL.B, enabled=0, range=psdk.RANGE.mV500)
scope.set_channel(channel=psdk.CHANNEL.C, enabled=0, range=psdk.RANGE.mV500)
scope.set_channel(channel=psdk.CHANNEL.D, enabled=0, range=psdk.RANGE.mV500)
scope.set_simple_trigger(channel=channel, threshold_mv=200, direction=psdk.TRIGGER_DIR.RISING, auto_trigger_ms=0)

# Setup SigGen
scope.set_siggen(frequency=1000, pk2pk=0.9, wave_type=psdk.WAVEFORM.SINE)

# Acquisition parameters 
nSamples = 1000
nCaptures = 100

pk2pk_values = []
waveforms = []  # Store each waveform

# Set capture timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500,
                                         unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Main capture loop
for _ in range(nCaptures):
    # Simple block capture
    channel_buffer, time_axis = scope.run_simple_block_capture(
        timebase=TIMEBASE,
        samples=nSamples,
        time_unit=psdk.TIME_UNIT.US,
    )

    # Add channel data to list
    waveform = channel_buffer[channel]
    waveforms.append(waveform)

    # Calculate pk2pk values, add to list
    pk2pk = np.ptp(waveform)
    pk2pk_values.append(pk2pk)

# Convert to numpy arrays
pk2pk_values = np.array(pk2pk_values)
waveforms = np.array(waveforms)

# Calculate statistics
print(f"Mean Pk-Pk: {np.mean(pk2pk_values):.2f} mV")
print(f"Std Dev Pk-Pk: {np.std(pk2pk_values):.2f} mV")

# Setup pyplot subplots
fig, axs = plt.subplots(2, 1, figsize=(10, 8))

# Top subplot: Overlay of all waveforms
for waveform in waveforms:
    axs[0].plot(time_axis, waveform, alpha=0.3)
axs[0].set_xlabel("Time (\u03bcs)")
axs[0].set_ylabel("Amplitude (mV)")
axs[0].set_title(f"Overlay of {nCaptures} Waveforms")
axs[0].grid(True)

# Bottom subplot: Histogram of pk2pk values
axs[1].hist(pk2pk_values, bins=20, edgecolor='black')
axs[1].set_xlabel("Peak-to-Peak Voltage (mV)")
axs[1].set_ylabel("Count")
axs[1].set_title(f"Histogram of Pk-Pk over {nCaptures} Captures")
axs[1].grid(True)

# Display pyplot
plt.tight_layout()
plt.show()
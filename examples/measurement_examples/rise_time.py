import pypicosdk as psdk
from matplotlib import pyplot as plt
import numpy as np

# Pico examples use inline argument values for clarity

# Capture configuration
SAMPLES = 5_000

def max_value(data):
    return np.max(data)

def min_value(data):
    return np.min(data)

def peak_to_peak(data):
    return max_value(data) - min_value(data)

def rise_time(data, time_axis):
    # Calculate lower (10%) and upper (90%) thresholds
    min_val = min_value(data)
    pk_pk = peak_to_peak(data)
    low = min_val + 0.1 * pk_pk
    high = min_val + 0.9 * pk_pk

    # Get time delta between samples
    t = time_axis[1] - time_axis[0]

    # Get indexes of high and low data
    high_index = np.where(data > high)[0]
    low_index = np.where(data < low)[0]

    # Find where a high sample goes to low and how many counts between
    rise_time_samples = []
    for i in high_index:
        if i+1 not in high_index:
            for x in range(1000):
                if i+x in low_index:
                    rise_time_samples.append(x+1)
                    break

    # Calculate average
    rise_time_samples = np.array(rise_time_samples)
    average = rise_time_samples.mean()

    # Return sample counts multiplied by time delta
    return average * t

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=1_000_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SQUARE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500, unit=psdk.SAMPLE_RATE.MSPS)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

print(f'Rise time(ns): {rise_time(channel_buffer[psdk.CHANNEL.A], time_axis)}')

# Plot data to pyplot
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])

# Add labels to pyplot
plt.xlabel("Time (ns)")     
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()

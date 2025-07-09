import pypicosdk as psdk
from matplotlib import pyplot as plt

# Pico examples use inline argument values for clarity

# Capture configuration
SAMPLES = 5_000

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=1_000_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500, unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Plot data to pyplot
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A])

# Add labels to pyplot
plt.xlabel("Time (ns)")     
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()

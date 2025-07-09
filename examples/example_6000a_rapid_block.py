import pypicosdk as psdk
from matplotlib import pyplot as plt

# Pico examples use inline argument values for clarity

# Configuration
SAMPLES = 1000
CAPTURES = 4

# Initialise device
scope = psdk.ps6000a()
scope.open_unit()

# Setup capture parameters (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Setup SigGen
scope.set_siggen(frequency=100_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run rapid block capture
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    n_captures=CAPTURES,
)

scope.close_unit()

# Overlay all captures on a single plot
for wf in buffers[psdk.CHANNEL.A]:
    plt.plot(time_axis, wf, alpha=0.3)
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()

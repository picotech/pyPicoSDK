import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
TIMEBASE = 2
SAMPLES = 50_000
CHANNEL_A = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1

# Initialise PicoScope 6000 Series A
scope = psdk.ps6000a()
scope.open_unit()

# Configure channel and AUX trigger
scope.set_channel(channel=CHANNEL_A, range=RANGE)
# Ensure AUX IO is configured as an input
scope.set_aux_io_mode(psdk.AUXIO_MODE.INPUT)
# Use the dedicated AUX trigger input instead of a channel
scope.set_simple_trigger(psdk.CHANNEL.TRIGGER_AUX, threshold_mv=1)

# Run the block capture
buffers, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Plot the captured data
plt.plot(time_axis, buffers[CHANNEL_A])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.ylim(-500, 500)
plt.grid(True)
plt.show()

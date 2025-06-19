import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
TIMEBASE = 2
SAMPLES = 50_000
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Configure AUX IO connector for triggering
scope.set_aux_io_mode(psdk.AUXIO_MODE.INPUT)

# Enable Channel A
scope.set_channel(channel=CHANNEL, range=RANGE)

# Trigger when AUX input is asserted
condition = psdk.PICO_CONDITION(psdk.CHANNEL.TRIGGER_AUX, psdk.PICO_TRIGGER_STATE.TRUE)
scope.set_trigger_channel_conditions([condition])
scope.set_simple_trigger(channel=psdk.CHANNEL.TRIGGER_AUX, threshold_mv=0)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Plot data
plt.plot(time_axis, channel_buffer[CHANNEL], label="Channel A")
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.legend()
plt.grid(True)
plt.show()

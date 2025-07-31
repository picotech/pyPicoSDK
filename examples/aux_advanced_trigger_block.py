import pypicosdk as psdk
from matplotlib import pyplot as plt

# Pico examples use inline argument values for clarity

# Capture configuration
SAMPLES = 50_000

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup SigGen to swing above 1.25 V threshold (1.5 Vpk)
# For demo, split SigGen output to TRIGGER_AUX and Channel A input
scope.set_siggen(frequency=1000, pk2pk=3, wave_type=psdk.WAVEFORM.SINE)

# Enable Channel A (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Configure an advanced trigger using the AUX input
# Threshold parameters are ignored; AUX triggers at 1.25 V
scope.set_advanced_trigger(
    channel=psdk.CHANNEL.TRIGGER_AUX,
    state=psdk.TRIGGER_STATE.TRUE,
    direction=psdk.THRESHOLD_DIRECTION.RISING,
    threshold_mode=psdk.THRESHOLD_MODE.LEVEL,
    threshold_upper_mv=0,
    threshold_lower_mv=0,
)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run the block capture
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Finish with PicoScope
scope.close_unit()

# Plot data
plt.plot(time_axis, channel_buffer[psdk.CHANNEL.A], label="Channel A")
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.legend()
plt.grid(True)
plt.show()

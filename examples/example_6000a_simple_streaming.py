import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
sample_interval = 1
sample_units = psdk.PICO_TIME_UNIT.US
samples = 5000
channel_a = psdk.CHANNEL.A
range = psdk.RANGE.V1

# SigGen variables
siggen_frequency = 1000  # Hz
siggen_pk2pk = 2  # Volts peak-to-peak

# Initialise PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Output a sine wave to help visualise captured data
scope.set_siggen(siggen_frequency, siggen_pk2pk, psdk.WAVEFORM.SINE)

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Run streaming capture
channels, time_axis = scope.run_simple_streaming_capture(
    sample_interval=sample_interval,
    sample_interval_time_units=sample_units,
    samples=samples,
    auto_stop=True,
    datatype=psdk.DATA_TYPE.INT16_T,
    ratio_mode=psdk.RATIO_MODE.RAW,
)

# Finish with PicoScope
scope.close_unit()

# Plot data to pyplot
plt.plot(time_axis, channels[channel_a])
plt.xlabel("Time (s)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)
plt.show()


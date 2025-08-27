"""
This example is an advanced PicoScope example with minimal abstraction.
This will return the raw ctypes ADC data as samples.
"""

from matplotlib import pyplot as plt
import pypicosdk as psdk

# Pico examples use inline argument values for clarity

# Capture configuration
SAMPLES = 100000
PRE_TRIG = 50  # %

# Initialise PicoScope
scope = psdk.ps6000a()
scope.open_unit()
print(scope.get_unit_serial())

# Set siggen
scope.set_siggen(frequency=1_000, pk2pk=0.8, wave_type=psdk.WAVEFORM.SINE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Preferred: convert sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Run block capture and retrieve values
channels_buffer = scope.set_data_buffer_for_enabled_channels(samples=SAMPLES)
scope.run_block_capture(timebase=TIMEBASE, samples=SAMPLES, pre_trig_percent=PRE_TRIG)
scope.get_values(SAMPLES)

# No ADC to mV conversion, add it here
channels_buffer = scope.adc_to_mv(channels_buffer)
time_axis = scope.get_time_axis(TIMEBASE, SAMPLES, pre_trig_percent=PRE_TRIG)

# Finish with PicoScope
scope.close_unit()

# Create a single plot for the time series
plt.plot(time_axis, channels_buffer[psdk.CHANNEL.A])
plt.title('Time Series of Channel A')
plt.xlabel('Time (ns)')
plt.ylabel('Voltage (mV)')
plt.show()

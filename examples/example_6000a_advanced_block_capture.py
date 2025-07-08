#########################################################################
# This example is an advanced PicoScope example with minimal abstraction.
# This will return the raw ctypes ADC data as samples. 
#
#########################################################################

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Setup variables
samples = 100000
channel = psdk.CHANNEL.A
range = psdk.RANGE.V1

# Initialise PicoScope
scope = psdk.ps6000a()
scope.open_unit()
print(scope.get_unit_serial())

# Set capture timebase
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=500,
                                         unit=psdk.SAMPLE_RATE.MSPS)
# TIMEBASE = 2  # direct driver timebase
# TIMEBASE = scope.interval_to_timebase(20E-9)

# Setup channels and trigger
scope.set_channel(channel=channel, range=range)
scope.set_simple_trigger(channel=channel, threshold_mv=0) 

# Run block capture and retrieve values
channels_buffer = scope.set_data_buffer_for_enabled_channels(samples=samples)
scope.run_block_capture(timebase=TIMEBASE, samples=samples)
scope.get_values(samples)

# No ADC to mV conversion, add it here

# Finish with PicoScope
scope.close_unit()

# Build a Histogram of data
plt.figure(0)
plt.hist(channels_buffer[channel])
plt.savefig('histogram_6000a.png')

# Plot a graph of data
plt.figure(1)
plt.plot(channels_buffer[channel])
plt.savefig('graph_6000a.png')

#########################################################################
# This example is an advanced PicoScope example with minimal abstraction.
# This will return the raw ctypes ADC data as samples. 
#
#########################################################################

import pypicosdk as psdk
from matplotlib import pyplot as plt

timebase = 2
samples = 100000
channel = psdk.CHANNEL.A
range = psdk.RANGE.V1

scope = psdk.ps6000a()

scope.open_unit()

print(scope.get_unit_serial())
scope.set_channel(channel=channel, range=range)
scope.set_simple_trigger(channel=channel, threshold_mv=0) 

channels_buffer = scope.set_data_buffer_for_enabled_channels(samples=samples)
scope.run_block_capture(timebase=timebase, samples=samples)
scope.get_values(samples)

# No ADC conversion or time-axis yet

scope.close_unit()

# Histogram
plt.figure(0)
plt.hist(channels_buffer[channel])
plt.savefig('histogram_6000a.png')

# Graph
plt.figure(1)
plt.plot(channels_buffer[channel])
plt.savefig('graph_6000a.png')


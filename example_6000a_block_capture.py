import pypicosdk as psdk
from matplotlib import pyplot as plt

timebase = 2
samples = 100000
channel = psdk.CHANNEL.A
range = psdk.RANGE.V1

ps6000 = psdk.ps6000a()

ps6000.open_unit()

print(ps6000.get_unit_serial())
ps6000.set_channel(channel=channel, range=range)
ps6000.set_simple_trigger(channel=channel, threshold_mv=0) 

channels_buffer = ps6000.set_data_buffer_for_enabled_channels(samples=samples)
ps6000.run_block_capture(timebase=timebase, samples=samples)
ps6000.get_values(samples)

# No ADC conversion or time-axis yet

ps6000.close_unit()

# Histogram
plt.figure(0)
plt.hist(channels_buffer[channel])
plt.savefig('histogram_6000a.png')

# Graph
plt.figure(1)
plt.plot(channels_buffer[channel])
plt.savefig('graph_6000a.png')


from picosdk.picosdk import *
from matplotlib import pyplot as plt


timebase = 2
samples = 100000

ps6000 = ps6000a()

ps6000.open_unit()

print(ps6000.get_unit_serial())
ps6000.set_channel_on(channel=CHANNEL_A, range=RANGE_1V)
ps6000.set_simple_trigger(channel=CHANNEL_A, threshold_mv=0)

channels_buffer = ps6000.set_data_buffer_for_enabled_channels(samples=samples)
buffer = ps6000.run_block_capture(timebase=timebase, samples=samples)
ps6000.get_values(samples)

channels_buffer = ps6000.buffer_adc_to_mv_multiple_channels(channels_buffer)

ps6000.close_unit()

# Histogram
plt.figure(0)
plt.hist(channels_buffer[CHANNEL_A])
plt.savefig('histogram_6000a.png')

# Graph
plt.figure(1)
plt.plot(channels_buffer[CHANNEL_A])
plt.savefig('graph_6000a.png')


from picosdk import picosdk
from matplotlib import pyplot as plt


timebase = 2
samples = 100000
channel = picosdk.CHANNEL_A
range = picosdk.RANGE._1V

ps6000 = picosdk.ps6000a()

ps6000.open_unit()

print(ps6000.get_unit_serial())
ps6000.set_channel_on(channel=channel, range=range)
ps6000.set_simple_trigger(channel=channel, threshold_mv=0)

channels_buffer = ps6000.set_data_buffer_for_enabled_channels(samples=samples)
buffer = ps6000.run_block_capture(timebase=timebase, samples=samples)
ps6000.get_values(samples)

channels_buffer = ps6000.buffer_adc_to_mv_multiple_channels(channels_buffer)

ps6000.close_unit()

# Histogram
plt.figure(0)
plt.hist(channels_buffer[channel])
plt.savefig('histogram_6000a.png')

# Graph
plt.figure(1)
plt.plot(channels_buffer[channel])
plt.savefig('graph_6000a.png')


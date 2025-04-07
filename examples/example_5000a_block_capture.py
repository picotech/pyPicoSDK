import pypicosdk as psdk
from matplotlib import pyplot as plt

ps5000 = psdk.ps5000a()

range = psdk.RANGE._1V
timebase = 2
samples = 10000
channel_a = psdk.CHANNEL.A
channel_b = psdk.CHANNEL.B

range = psdk.RANGE._1V

ps5000.open_unit()

ps5000.open_unit(resolution=psdk.RESOLUTION._16BIT)
ps5000.change_power_source(psdk.POWER_SOURCE.SUPPLY_NOT_CONNECTED)

print(ps5000.get_unit_serial())
ps5000.set_channel(channel_a, range, coupling=psdk.DC_COUPLING)
ps5000.set_channel(channel_b, range, coupling=psdk.AC_COUPLING)
ps5000.set_simple_trigger(channel_b, 
                          threshold_mv=0, 
                          auto_trigger_ms=5000)

# Easy Block Capture
buffer = ps5000.run_simple_block_capture(timebase, samples)

ps5000.close_unit()


# print(buffer)
plt.plot(buffer[channel_a])
plt.plot(buffer[channel_b])
plt.savefig('graph.png')
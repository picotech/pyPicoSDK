import pypicosdk as psdk
from matplotlib import pyplot as plt

scope = psdk.ps5000a()

range = psdk.RANGE._1V
timebase = 2
samples = 10000
channel_a = psdk.CHANNEL.A
channel_b = psdk.CHANNEL.B

range = psdk.RANGE.V1

scope.open_unit()

scope.open_unit(resolution=psdk.RESOLUTION._16BIT)
scope.change_power_source(psdk.POWER_SOURCE.SUPPLY_NOT_CONNECTED)

print(scope.get_unit_serial())
scope.set_channel(channel_a, range, coupling=psdk.DC_COUPLING)
scope.set_channel(channel_b, range, coupling=psdk.AC_COUPLING)
scope.set_simple_trigger(channel_b, 
                          threshold_mv=0, 
                          auto_trigger_ms=5000)

# Easy Block Capture
buffer = scope.run_simple_block_capture(timebase, samples)

scope.close_unit()


# print(buffer)
plt.plot(buffer[channel_a])
plt.plot(buffer[channel_b])
plt.savefig('graph.png')
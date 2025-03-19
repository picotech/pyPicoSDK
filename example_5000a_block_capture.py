from picosdk.picosdk import *
from matplotlib import pyplot as plt

ps5000 = ps5000a()

range = RANGE_10V
threshold_mv = 2000
timebase = 32
samples = 5000

# raise PicoSDKNotFoundException('test', 'test')

ps5000.open_unit(resolution=FLEXRES_5000A_8BIT)
ps5000.change_power_source(POWER_SOURCE.SUPPLY_NOT_CONNECTED)

ps5000.get_unit_serial()

print("Serial:", ps5000.get_unit_serial())
ps5000.set_channel(CHANNEL_A, range, coupling=AC_COUPLING)
ps5000.set_channel(CHANNEL_B, range, coupling=AC_COUPLING)
# print("Timebase:", ps5000.get_timebase(timebase, samples))
ps5000.set_simple_trigger(CHANNEL_B, 
                          threshold_mv=threshold_mv, 
                          auto_trigger_ms=5000)

# Easy Block Capture
buffer = ps5000.run_block(timebase, samples)

ps5000.close_unit()

# df = pd.DataFrame.from_dict(buffer)
# df.to_csv('data.csv')


# print(buffer)
# buffer = ps5000.channels_buffer_adc_to_mv(buffer)
plt.plot(buffer[CHANNEL_A])
plt.plot(buffer[CHANNEL_B])
plt.savefig('graph.png')
from picosdk import *
from matplotlib import pyplot as plt
import pandas as pd
from time import sleep

ps6000 = ps6000a()

range = RANGE_10V
threshold_mv = 2000
timebase = 32
samples = 5000

ps6000.open_unit(FLEXRES_5000A_8BIT)
print(ps6000.get_unit_info(UNIT_INFO.PICO_USB_VERSION))
ps6000.close_unit()

exit()

ps6000.get_unit_info()

print("Serial:", ps6000.get_unit_serial())
ps6000.set_channel(CHANNEL_A, range)
ps6000.set_channel(CHANNEL_B, range, coupling=AC_COUPLING)
print("Timebase:", ps6000.get_timebase(timebase, samples))
ps6000.set_simple_trigger(CHANNEL_B, 
                          threshold_mv=threshold_mv, 
                          auto_trigger_ms=5000)

# Easy Block Capture
buffer = ps6000.run_block(timebase, samples)

ps6000.close_unit()

# df = pd.DataFrame.from_dict(buffer)
# df.to_csv('data.csv')


# print(buffer)
# buffer = ps5000.channels_buffer_adc_to_mv(buffer)
plt.plot(buffer[CHANNEL_A])
plt.plot(buffer[CHANNEL_B])
plt.savefig('graph.png')
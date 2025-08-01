import pypicosdk as psdk
from matplotlib import pyplot as plt
import time
import numpy as np

import csv

# Pico examples use inline argument values for clarity

# Capture configuration
timebase = 4
samples = 5_000
interval = 2
unit = psdk.TIME_UNIT.NS
pico_unit = psdk.PICO_TIME_UNIT.NS
channel = psdk.CHANNEL.A

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=10_000, pk2pk=1.6, wave_type=psdk.WAVEFORM.SINE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

timebase = scope.interval_to_timebase(2, unit)

buffer = scope.set_data_buffer(channel, samples)
scope.run_streaming(
    sample_interval=interval,
    time_units=pico_unit,
    max_pre_trigger_samples=0,
    max_post_trigger_samples=250,
    auto_stop=0,
    ratio=0,
    ratio_mode=psdk.RATIO_MODE.RAW
)
np_array = []
info_array = []
reserve = np.array([5E4])
count = 0
for x in range(200):
    for i in range(4):
        # np_array.append([count])
        info = scope.get_streaming_latest_values(
            channel=channel,
            ratio_mode=psdk.RATIO_MODE.RAW,
            data_type=psdk.DATA_TYPE.INT16_T
        )
        # print('Capture', count, info)
        info['count'] = count
        count += 1
        n_samples = info['no of samples']
        start_index = info['start index']
        if n_samples > 0:
            np_array.append(buffer[start_index:start_index+n_samples])
            info_array.append(info)
        if info['status'] == 407:
            buffer = scope.set_data_buffer(channel, samples, segment=i*samples, action=psdk.ACTION.ADD)

scope.stop()
scope.close_unit()

with open('data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=info_array[0].keys())
    writer.writeheader()
    writer.writerows(info_array)

array = np.concatenate(np_array)

np.savetxt("samples.csv", array, delimiter=",", fmt='%d')

plt.plot(array)
plt.show()
print(array)


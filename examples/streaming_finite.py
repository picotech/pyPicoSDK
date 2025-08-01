import pypicosdk as psdk
from matplotlib import pyplot as plt
import time
import numpy as np

import csv

# Pico examples use inline argument values for clarity

# Capture configuration
timebase = 4
samples = 5_000
streaming_samples = 250
no_of_stream_buffers = 300
interval = 4
unit = psdk.TIME_UNIT.NS
pico_unit = psdk.PICO_TIME_UNIT.NS
channel = psdk.CHANNEL.A

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=100, pk2pk=1.6, wave_type=psdk.WAVEFORM.TRIANGLE)

# Setup channels and trigger (inline arguments)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

timebase = scope.interval_to_timebase(2, unit)

def streaming_loop():
    # Create initial buffer
    buffer = scope.set_data_buffer(channel, samples, segment=0)

    # Run streaming
    scope.run_streaming(
        sample_interval=interval,
        time_units=pico_unit,
        max_pre_trigger_samples=0,
        max_post_trigger_samples=streaming_samples,
        auto_stop=0,
        ratio=0,
        ratio_mode=psdk.RATIO_MODE.RAW
    )

    # Create data arrays to populate
    np_array = []
    info_array = []
    buffer_index = 0
    for x in range(no_of_stream_buffers):
        info = scope.get_streaming_latest_values(
            channel=channel,
            ratio_mode=psdk.RATIO_MODE.RAW,
            data_type=psdk.DATA_TYPE.INT16_T
        )
        n_samples = info['no of samples']
        start_index = info['start index']
        # If buffer isn't empty, add data to array
        if n_samples > 0:
            np_array.append(buffer[start_index:start_index+n_samples])
            info_array.append(info)
        # If buffer full, create new buffer
        if info['status'] == 407:
            buffer = (buffer + 1) % 2 # Switch between buffer segment index 0*samples and 1*samples
            buffer = scope.set_data_buffer(channel, samples, segment=buffer_index*samples, action=psdk.ACTION.ADD)

    np_array = np.concatenate(np_array)
    return np_array, info_array

np_array, info_array = streaming_loop()

scope.stop()
scope.close_unit()



with open('data.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=info_array[0].keys())
    writer.writeheader()
    writer.writerows(info_array)

print('Dropped buffers:',int(no_of_stream_buffers-(len(np_array)/samples)))

np.savetxt("samples.csv", np_array, delimiter=",", fmt='%d')

plt.plot(np_array)
plt.show()


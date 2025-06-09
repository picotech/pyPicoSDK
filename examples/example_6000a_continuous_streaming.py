import pypicosdk as psdk
from matplotlib import pyplot as plt
from collections import deque
import time

# Setup variables
sample_interval = 1
sample_units = psdk.PICO_TIME_UNIT.US
plot_samples = 5000  # samples shown on screen
chunk_samples = 1000  # number of samples to read per iteration
channel_a = psdk.CHANNEL.A
voltage_range = psdk.RANGE.V1

# Initialise PicoScope 6000
scope = psdk.ps6000a()
scope.open_unit()

# Setup channels and trigger
scope.set_channel(channel=channel_a, range=voltage_range)
scope.set_simple_trigger(channel=channel_a, threshold_mv=0)

# Allocate buffers for streaming
channels_buffer = scope.set_data_buffer_for_enabled_channels(chunk_samples)

# Start streaming with FIFO up to 4G samples
auto_stop = 0
actual_interval = scope.run_streaming(
    sample_interval,
    sample_units,
    0,
    4_000_000_000,
    auto_stop,
    1,
    psdk.RATIO_MODE.RAW,
)

seconds_per_sample = {
    psdk.PICO_TIME_UNIT.FS: 1e-15,
    psdk.PICO_TIME_UNIT.PS: 1e-12,
    psdk.PICO_TIME_UNIT.NS: 1e-9,
    psdk.PICO_TIME_UNIT.US: 1e-6,
    psdk.PICO_TIME_UNIT.MS: 1e-3,
    psdk.PICO_TIME_UNIT.S: 1,
}[sample_units] * actual_interval

# Setup matplotlib for interactive plotting
plt.ion()
fig, ax = plt.subplots()
line, = ax.plot([], [])
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude (mV)")
ax.grid(True)

# Rolling buffers for plot data
time_axis = deque(maxlen=plot_samples)
values = deque(maxlen=plot_samples)

collected = 0
trigger_info = psdk.PICO_STREAMING_DATA_TRIGGER_INFO()

try:
    while True:
        data_array = (psdk.PICO_STREAMING_DATA_INFO * 1)()
        data_array[0].channel_ = channel_a
        data_array[0].mode_ = psdk.RATIO_MODE.RAW
        data_array[0].type_ = psdk.DATA_TYPE.INT16_T
        data_array[0].noOfSamples_ = chunk_samples
        data_array[0].bufferIndex_ = 0
        data_array[0].startIndex_ = 0
        data_array[0].overflow_ = 0

        scope.get_streaming_latest_values(data_array, trigger_info)
        num = data_array[0].noOfSamples_
        if num == 0:
            time.sleep(0.01)
            continue

        data = [scope.adc_to_mv(sample, voltage_range) for sample in channels_buffer[channel_a][:num]]
        for i in range(num):
            time_axis.append((collected + i) * seconds_per_sample)
            values.append(data[i])
        collected += num

        line.set_data(list(time_axis), list(values))
        if time_axis:
            ax.set_xlim(time_axis[0], time_axis[-1])
        plt.pause(0.001)
except KeyboardInterrupt:
    pass

# Finish with PicoScope
scope.close_unit()
plt.ioff()
plt.show()

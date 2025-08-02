import pypicosdk as psdk
from matplotlib import pyplot as plt
import numpy as np
import threading
import time

# Capture configuration
timebase = 4
samples = 5_000
streaming_samples = 250
no_of_stream_buffers = 300
interval = 4
unit = psdk.TIME_UNIT.NS
pico_unit = psdk.PICO_TIME_UNIT.NS
channel = psdk.CHANNEL.A


def setup_scope():
    scope = psdk.ps6000a()
    scope.open_unit()
    scope.set_siggen(frequency=100, pk2pk=1.6, wave_type=psdk.WAVEFORM.TRIANGLE)
    scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
    scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)
    return scope

class StreamingScope:
    def __init__(self, scope:psdk.ps6000a):
        self.scope = scope
        self.stop_event = threading.Event()

    def setup_streaming(self):
        # Setup empty variables for streaming
        self.np_list = []
        self.np_array = []
        self.info_array = []
        self.buffer_index = 0
        # Setup initial buffer for streaming
        buffer = self.scope.set_data_buffer(channel, samples, segment=0)
        # start streaming
        self.scope.run_streaming(
            sample_interval=interval,
            time_units=pico_unit,
            max_pre_trigger_samples=0,
            max_post_trigger_samples=streaming_samples,
            auto_stop=0,
            ratio=0,
            ratio_mode=psdk.RATIO_MODE.RAW
        )
        self.buffer = buffer
    
    def run_streaming(self):
        info = self.scope.get_streaming_latest_values(
            channel=channel,
            ratio_mode=psdk.RATIO_MODE.RAW,
            data_type=psdk.DATA_TYPE.INT16_T
        )
        n_samples = info['no of samples']
        start_index = info['start index']
        # If buffer isn't empty, add data to array
        if n_samples > 0:
            self.np_list.append(self.buffer[start_index:start_index+n_samples])
            self.np_array = np.concatenate(self.np_list)
            self.info_array.append(info)
        # If buffer full, create new buffer
        if info['status'] == 407:
            self.buffer = (self.buffer_index + 1) % 2 # Switch between buffer segment index 0*samples and 1*samples
            self.buffer = self.scope.set_data_buffer(channel, samples, segment=self.buffer_index*samples, action=psdk.ACTION.ADD)

    def run_streaming_while(self, stop=True):
        while not self.stop_event.is_set():
            self.run_streaming()

    def run_streaming_for(self, n_times):
        for i in range(n_times):
            self.run_streaming()

def streaming_thread(stream:StreamingScope):
    stream.run_streaming_while()

def main():
    stop = False
    scope = setup_scope()
    stream = StreamingScope(scope)
    stream.setup_streaming()

    th = threading.Thread(target=streaming_thread, args=[stream])
    th.start()

    time.sleep(5)

    stream.stop_event.set()
    th.join()

    scope.close_unit()

    plt.plot(stream.np_array)
    plt.show()


if __name__ == '__main__':
    main()
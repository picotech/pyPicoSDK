"""
Note: RACE CONDITION!
The data retrieved from get_streaming data *NEEDS* to be 
    larger than the captured data. 
    If it's smaller, the live plot will lag behind the data. 
    If it's larger, the streaming will ignore the empty buffers.

Threading: 
    The main streaming is handled in a thread while loop.
    This is so that the matplotlib animation can be the main loop,
    so the frame update interval doesn't control the retrieval of data
    removing any race condition from the animation.
"""


import pypicosdk as psdk
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import threading
import time

# Capture configuration
timebase = 4
samples = int(1E9)
streaming_samples = 250
interval = 20
display_samples = 1000
unit = psdk.TIME_UNIT.NS
pico_unit = psdk.PICO_TIME_UNIT.NS
channel = psdk.CHANNEL.A


fig = plt.figure() 
axis = plt.axes(xlim =(0, display_samples), 
                ylim =(-32000, 32000)) 
x = np.arange(display_samples)  # Predefined x-data of length 10
line, = axis.plot(x, np.zeros_like(x), lw=2)  # Initialize with zeros


def setup_scope():
    scope = psdk.ps6000a()
    scope.open_unit()
    scope.set_siggen(frequency=1_000_000, pk2pk=1.6, wave_type=psdk.WAVEFORM.TRIANGLE)
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
            # self.np_list.append(self.buffer[start_index:start_index+n_samples])
            self.np_list = self.buffer[start_index:start_index+n_samples]
            self.np_array = self.np_list
            # self.info_array = self.info_array.append(info)
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

def animate(frame, stream:StreamingScope):
    print(len(stream.np_array))
    data = stream.np_array[-display_samples:]
    line.set_ydata(data)
    return line,

def main():
    stop = False
    scope = setup_scope()
    stream = StreamingScope(scope)
    stream.setup_streaming()

    th = threading.Thread(target=streaming_thread, args=[stream])
    th.start()

    anim = FuncAnimation(fig, animate, frames=500, fargs=(stream, ), interval=20, blit=True)
    plt.show()

    stream.stop_event.set()
    th.join()

    scope.close_unit()


if __name__ == '__main__':
    main()
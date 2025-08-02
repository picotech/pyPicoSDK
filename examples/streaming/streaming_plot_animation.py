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
        self.stop_bool = False  # Bool to stop streaming while loop
        self.np_list = []   # List of retrieved np.ndarrays
        self.np_array = [] # Full concatenated np.ndarray
        self.info_array = []    # List of retrieved info per buffer
        self.buffer_index = 0   # Buffer segment index
        self.result_array = 'latest'    # Format to save data

    def config_streaming(
            self, 
            channel, 
            samples, 
            interval, 
            time_units,
            max_array_size,
            ratio=0,
            ratio_mode=psdk.RATIO_MODE.RAW,
            data_type=psdk.DATA_TYPE.INT16_T,
        ):
        self.channel = channel
        self.samples = samples
        self.interval = interval
        self.time_units = time_units
        self.np_array = np.zeros(shape=max_array_size)
        self.ratio = ratio
        self.ratio_mode = ratio_mode
        self.data_type = data_type

    def run_streaming(self):
        self.buffer_index = 0
        self.stop_bool = False
        # Setup empty variables for streaming
        # Setup initial buffer for streaming
        self.buffer = self.scope.set_data_buffer(self.channel, self.samples, segment=0)
        # start streaming
        self.scope.run_streaming(
            sample_interval=self.interval,
            time_units=self.time_units,
            max_pre_trigger_samples=0,
            max_post_trigger_samples=streaming_samples,
            auto_stop=0,
            ratio=self.ratio,
            ratio_mode=self.ratio_mode
        )
    
    def get_streaming_data(self):
        info = self.scope.get_streaming_latest_values(
            channel=self.channel,
            ratio_mode=self.ratio_mode,
            data_type=self.data_type
        )
        n_samples = info['no of samples']
        start_index = info['start index']
        # If buffer isn't empty, add data to array
        if n_samples > 0:
            # If data is wanted as a concatenated list use 'append' (for finite), 
            # for latest retrieved buffer, use 'latest' (while infitie)
            if self.result_array == 'append':
                self.np_list.append(self.buffer[start_index:start_index+n_samples])
                self.np_array = np.concatenate(self.np_list)
            elif self.result_array == 'latest':
                self.np_array = self.buffer[start_index:start_index+n_samples]
            # self.info_array = self.info_array.append(info)
        # If buffer full, create new buffer
        if info['status'] == 407:
            self.buffer = (self.buffer_index + 1) % 2 # Switch between buffer segment index 0*samples and 1*samples
            self.buffer = self.scope.set_data_buffer(
                self.channel, self.samples, 
                segment=self.buffer_index*self.samples, 
                action=psdk.ACTION.ADD)

    def run_streaming_while(self, stop=True):
        self.run_streaming()
        while not self.stop_bool:
            self.get_streaming_data()

    def run_streaming_for(self, n_times):
        self.run_streaming()
        for i in range(n_times):
            self.get_streaming_data()

    def stop(self):
        self.stop_bool = True

def streaming_thread(stream:StreamingScope):
    stream.run_streaming_while()

def animate(frame, stream:StreamingScope):
    data = stream.np_array[-display_samples:]
    line.set_ydata(data)
    return line,

def main():
    stop = False
    scope = setup_scope()
    stream = StreamingScope(scope)
    stream.config_streaming(channel, samples, interval, pico_unit, display_samples)

    th = threading.Thread(target=streaming_thread, args=[stream])
    th.start()

    anim = FuncAnimation(fig, animate, frames=500, fargs=(stream, ), interval=20, blit=True)
    plt.show()

    stream.stop()
    th.join()

    scope.close_unit()


if __name__ == '__main__':
    main()
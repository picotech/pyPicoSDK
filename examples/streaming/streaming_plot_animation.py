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
from pypicosdk.streaming import StreamingScope
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

def streaming_thread(stream:StreamingScope):
    stream.run_streaming_while()

def animate(frame, stream:StreamingScope):
    data = stream.buffer_array
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
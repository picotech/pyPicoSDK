"""
This is an example of single-channel streaming mode displayed to
a pyplot animation plot.

To do this it uses the StreamingScope class from pypicosdk.streaming
and runs a thread containing the streaming loop.

Downsampling:
    This streaming example uses AGGREGATE downsampling. This retrieves 2 buffer instead of 1.
    The two buffers are the MIN and MAX value over X samples, (X being ratio).
    The midpoint is calculated and displayed to pyplot.

    If using any other downsampling method, stream.buffer only outputs a single buffer.
"""
import numpy as np

from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

import pypicosdk as psdk
from pypicosdk.streaming import StreamingScope

# Capture configuration
SAMPLES = 10_000
INTERVAL = 1000
unit = psdk.TIME_UNIT.PS
channel = psdk.CHANNEL.A

# Downsample data using min/max aggregate
RATIO = 100000
ratio_mode = psdk.RATIO_MODE.AGGREGATE

# Setup classe objects
scope = psdk.psospa()


def setup_pyplot():
    """Sets up pyplot with empty data"""
    fig = plt.figure()
    axis = plt.axes(xlim=(0, SAMPLES), ylim=(-scope.min_adc_value, scope.max_adc_value))
    # Initialize with numpy array of zeros
    x = np.arange(SAMPLES)
    line, = axis.plot(x, np.zeros_like(x), lw=2)
    # Add a sweep line
    vline = axis.axvline(x=0, color='red')
    return fig, line, vline


def setup_scope():
    """Setup PicoScope and get scope class"""
    scope.open_unit()
    scope.set_siggen(frequency=1, pk2pk=1.6, wave_type=psdk.WAVEFORM.TRIANGLE)
    scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)


def get_data(stream):
    """Get data from streaming class based on ratio mode"""
    buffer = stream.get_data()
    index = stream.get_last_sample_index()
    # If AGGREGATE ratio mode, find midpoint
    if ratio_mode == psdk.RATIO_MODE.AGGREGATE:
        return (buffer[0] + buffer[1]) / 2, index
    return buffer, index


def animate(_frame, stream, line, vline):
    """pyplot animation thread"""
    buffer, index = get_data(stream)
    line.set_ydata(buffer)
    vline.set_xdata([index, index])
    return [line, vline]


def main():
    """Main function"""
    setup_scope()
    fig, line, vline = setup_pyplot()

    stream = StreamingScope(scope, channel, SAMPLES, INTERVAL, unit,
                            ratio=RATIO, ratio_mode=ratio_mode)
    stream.start()

    _ = FuncAnimation(fig, animate, frames=500, fargs=(stream, line, vline,),
                      interval=20, blit=True)
    plt.show()

    stream.stop()
    scope.close_unit()


if __name__ == '__main__':
    main()

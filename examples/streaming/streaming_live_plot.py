"""
This is an example of single-channelstreaming mode displayed to
a pyplot animation plot.

To do this it uses the StreamingScope class from pypicosdk.streaming
and runs a thread containing the streaming loop.
"""

import threading
import numpy as np

from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation

import pypicosdk as psdk
from pypicosdk.streaming import StreamingScope

# Capture configuration
SAMPLES = int(1E6)  # Maxmimum samples in scope memory
DISPLAY_SAMPLES = 10_000  # Samples of pyplot x-axis
DISPLAY_RATIO = SAMPLES // DISPLAY_SAMPLES  # Downsample ratio for display

INTERVAL = 10
pico_unit = psdk.TIME_UNIT.NS
channel = psdk.CHANNEL.A


def setup_pyplot():
    """Sets up pyplot with empty data"""
    fig = plt.figure()
    axis = plt.axes(xlim=(0, DISPLAY_SAMPLES),
                    ylim=(-32000, 32000))
    x = np.arange(DISPLAY_SAMPLES)  # Predefined x-data of length 10
    line, = axis.plot(x, np.zeros_like(x), lw=2)  # Initialize with zeros
    return fig, line


def setup_scope():
    """Setup PicoScope and get scope class"""
    scope = psdk.psospa()
    scope.open_unit()
    scope.set_siggen(frequency=10_000, pk2pk=1.6,
                     wave_type=psdk.WAVEFORM.TRIANGLE)
    scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
    scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)
    return scope


def streaming_thread(stream: StreamingScope):
    """Streaming thread"""
    stream.start_streaming_while()


def animate(_, line, stream: StreamingScope):
    """pyplot animation thread"""

    # Print streaming rate in MS/s
    print(f'Min/Max/Avg: {stream.msps_min}, {stream.msps_max}'
          f', {stream.msps_avg} MS/s')

    # Get streaming data and update pyplot
    data = stream.buffer[::DISPLAY_RATIO]
    line.set_ydata(data)
    return [line]


def main():
    """Main function"""
    fig, line = setup_pyplot()

    scope = setup_scope()
    stream = StreamingScope(scope)
    stream.config_streaming(channel, SAMPLES, INTERVAL, pico_unit)

    th = threading.Thread(target=streaming_thread, args=[stream])
    th.start()

    _ = FuncAnimation(fig, animate, frames=500, fargs=(line, stream, ),
                      interval=20, blit=True)
    plt.show()

    stream.stop()
    th.join()

    scope.close_unit()


if __name__ == '__main__':
    main()

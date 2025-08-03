import pypicosdk as psdk
from pypicosdk.streaming import StreamingScope
from matplotlib import pyplot as plt
import numpy as np

# Capture configuration
timebase = 4
samples = int(1E9)
streaming_samples = 250
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

def main():
    scope = setup_scope()
    stream = StreamingScope(scope)
    stream.config_streaming(channel, samples, interval, pico_unit, max_buffer_size=None)

    stream.run_streaming_for_samples(5000000)

    scope.close_unit()

    plt.plot(stream.buffer_array)
    plt.show()


if __name__ == '__main__':
    main()
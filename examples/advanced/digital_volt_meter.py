"""
Copyright (C) 2018-2022 Pico Technology Ltd. See LICENSE file for terms.

This example sets up the PicoScope as a single channel digital multimeter.
It measures the DC output of the SigGen and prints the average voltage of a single capture.
No trigger is used in this example (None/Free).

This example uses advanced block capture, to reduce setting up the buffer multiple times.

Setup:
    - Connect channel A to SigGen output.
"""
import time
from pypicosdk import ps6000a, CHANNEL, RANGE, WAVEFORM, TIME_UNIT

scope = ps6000a()

# Channel setup
channel = CHANNEL.A
v_range = RANGE.V1

# Capture setup
INTERVAL = 1
unit = TIME_UNIT.MS
SAMPLES = 100
REFRESH_RATE = 0.1

# SigGen setup
waveform = WAVEFORM.DC_VOLTAGE
OFFSET = 0.8


def setup_scope():
    "Setup PicoScope"
    scope.open_unit()
    scope.set_channel(channel, v_range)
    scope.set_siggen(0, 0, waveform, OFFSET)
    buffer = scope.set_data_buffer(channel, SAMPLES)
    timebase = scope.interval_to_timebase(INTERVAL, unit)
    return buffer, timebase


def main():
    "Main function"
    buffer, timebase = setup_scope()
    while True:
        scope.run_block_capture(timebase, SAMPLES)
        scope.get_values(SAMPLES)
        avg_volts = scope.adc_to_volts(buffer.mean(), channel)
        print(f'{avg_volts:.2f} V')
        time.sleep(REFRESH_RATE)


if __name__ == '__main__':
    main()

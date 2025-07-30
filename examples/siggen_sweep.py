"""
This example produces a sweep sine wave out of the AWG. 

Setup:
1. Plug 1 BNC end into AWG SigGen output of python PicoScope.
2. Plug other BNC end into a seperate PicoScope to verify
    the sweep waveform.
3. This example uses input() to keep PicoScope open, press
    return in console to exit example.
"""

import pypicosdk as psdk
from matplotlib import pyplot as plt

# Open PicoScope
scope = psdk.ps6000a()
scope.open_unit()

# Create sweeping sine waveform
scope.set_siggen(
    frequency=1000, # 1000 Hz
    pk2pk=0.8,  # 0.8 Vpk2pk
    wave_type=psdk.WAVEFORM.SINE, # Sine wave
    sweep=True, # Turn sweep on
    stop_freq=5000, # Stop at 5000 Hz
    inc_freq=1, # Increment 1 Hz per step
    dwell_time=0.001,   # Increment every 1 ms
    sweep_type=psdk.SWEEP_TYPE.UP   # Sweep upwards
)

input('Return to finish...')    # Wait for user input before exiting

# Close Device
scope.close_unit()

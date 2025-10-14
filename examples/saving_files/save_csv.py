"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Description:
This example completes a simple block capture and saves the data from channel A to disk.
The example uses numpy to stack the data into a single array and saves it via
np.savetxt().

CSV files are not as efficient as numpy binary file (.npy). If you want to save the data
to be human-readable, CSV is a good option. If you are saving it to load into another Python
script, consider using np.save(): detailed in examples/saving_files/save_numpy.py example.

Requirements:
- PicoScope 6000E/3000E
- Python packages:
  (pip install) pypicosdk numpy

Setup:
  - Connect Channel A to the AWG output
"""

import numpy as np
import pypicosdk as psdk

SAMPLES = 5_000

# This example uses the same setup as 'simple_block_capture.py', setup comments are skipped.
scope = psdk.ps6000a()
scope.open_unit()
scope.set_siggen(frequency=50_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold=0, auto_trigger=0)
TIMEBASE = scope.sample_rate_to_timebase(sample_rate=50, unit=psdk.SAMPLE_RATE.MSPS)

# Get data to save as channel buffer and time axis
channel_buffer, time_axis = scope.run_simple_block_capture(TIMEBASE, SAMPLES)

# Close the unit as it's no longer needed
scope.close_unit()

# If you'd like to plot the data before saving, do it here

# Combine the "time_axis" & "channel_buffer" arrays *vertically* using column_stack
a_buffer_time = np.column_stack([time_axis, channel_buffer[psdk.CHANNEL.A]])

# Save the combined 2D array to a_buffer_time.csv using np.savetxt
np.savetxt(
    'a_buffer_time.csv',         # Name of file (must end in .csv)
    a_buffer_time,               # 2D Numpy array to be saved
    delimiter=',',               # ',' is commonly used as delimiter in CSV files
    header='Time,ChannelA',      # Column headers, seperated by delimiter
    comments=''                  # NumPy uses #code comments as column headings, force clean headers
    )

"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Description:
This example follows on from 'save_numpy.py' to load and plot the data saved.

Requirements:
- PicoScope 6000E/3000E
- Python packages:
  (pip install) numpy matplotlib

Notes:
  pypicosdk isn't needed. Any ADC/mV conversions cannot be made via scope.adc_to_mv() as
  that function uses the PicoScope setup to calculate the millivolt/volt value.

Setup:
  - Make sure you have ran 'save_numpy.py' previously to save the data to disk.
"""

import numpy as np
from matplotlib import pyplot as plt

# Load Channel A buffer and time axis from their seperate files and plot to pyplot
a_buffer = np.load('a_buffer.npy')
time_axis = np.load('time_axis.npy')

# Plot seperate arrays to the first subplot
plt.subplot(2, 1, 1)
plt.plot(time_axis, a_buffer, color='tab:blue')

# Add labels to subplot
plt.title('Seperate NumPy Files')
plt.ylim([-1000, 1000])
plt.ylabel("Amplitude (mV)")
plt.grid(True)

# OR load using the combined numpy file
a_buffer_time = np.load('a_buffer_time.npy')

# Plot combined array to second subplot
plt.subplot(2, 1, 2)
plt.plot(a_buffer_time[0], a_buffer_time[1], color='tab:orange')

# Add labels to second subplot
plt.title('Combined NumPy Files')
plt.ylim([-1000, 1000])
plt.xlabel("Time (ns)")
plt.ylabel("Amplitude (mV)")
plt.grid(True)

# Display both plots
plt.tight_layout()
plt.show()

"""
Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms.

Timebase calculation example for a PicoScope 6000E device

Pico devices use sample rates from a fixed list of enumerated values,
pyPicoSDK allows users to specify a requested sample rate/ interval and will choose the
closest enum value to set the device to.
The actual sample rate/interval is then returned to the application

Description:
  Shows how to determine the correct timebase value for a specific
  sampling interval.

Requirements:
- PicoScope 6000E
- Python packages:
  (pip install) pypicosdk
"""

# Instead of importing the whole pyPicoSDK lib, here we unpack only the needed enums
# allowing them to be referenced directly in below methods
from pypicosdk import ps6000a, CHANNEL, RANGE, SAMPLE_RATE, TIME_UNIT

# Create "scope" class and initialize PicoScope
scope = ps6000a()
scope.open_unit()

# Setup channels to make sure sample interval is accurate (direct enum reference)
scope.set_channel(CHANNEL.A, RANGE.V1)
scope.set_channel(CHANNEL.C, RANGE.mV100)

# Print the result of asking for a sample rate of 100MS/s
# (normally this would not be printed as directly sets the device to the nearest timebase)
print(scope.sample_rate_to_timebase(200, unit=SAMPLE_RATE.MSPS))

# Print the result of asking for a sampple interval of 10ns
# (normally this would not be printed as directly sets the device to the nearest timebase)
print(scope.interval_to_timebase(5, unit=TIME_UNIT.NS))

# Unlike the above two helper functions, which return the closest timebase (int) this direct call
# to the driver returns the actual response as a python dict.
print(scope.get_nearest_sampling_interval(5E-9))

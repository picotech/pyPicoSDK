"""
Example to figure out the correct timebase value for a specific interval.
"""
from pypicosdk import ps6000a, CHANNEL, RANGE

# Variables
interval_s = 10E-9 # 10 us

# Open PicoScope 6000
scope = ps6000a()
scope.open_unit()

# Setup channels to make sure sample interval is accurate
scope.set_channel(CHANNEL.A, RANGE.V1)
scope.set_channel(CHANNEL.C, RANGE.mV100)

# Return suggested timebase and actual sample interval 
print(scope.get_nearest_sampling_interval(10E-12))

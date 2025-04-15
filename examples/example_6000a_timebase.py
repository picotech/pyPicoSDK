"""
Example to figure out the correct timebase value for a specific interval.
"""
from pypicosdk import ps6000a, CHANNEL, RANGE, SAMPLE_RATE, TIME_UNIT

# Variables
interval_s = 10E-9 # 10 us

# Open PicoScope 6000
scope = ps6000a()
scope.open_unit()

# Setup channels to make sure sample interval is accurate
scope.set_channel(CHANNEL.A, RANGE.V1)
scope.set_channel(CHANNEL.C, RANGE.mV100)

# Return suggested timebase and actual sample interval 
print(scope.sample_rate_to_timebase(100, unit=SAMPLE_RATE.MSPS))
print(scope.interval_to_timebase(0.001, unit=TIME_UNIT.US))
print(scope.get_nearest_sampling_interval(1E-9))

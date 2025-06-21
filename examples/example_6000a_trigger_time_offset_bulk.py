import pypicosdk as psdk

# Capture configuration
TIMEBASE = 2
SAMPLES = 1000
CAPTURES = 4
CHANNEL = psdk.CHANNEL.A
RANGE = psdk.RANGE.V1

# Initialize and configure the scope
scope = psdk.ps6000a()
scope.open_unit()
scope.set_channel(CHANNEL, RANGE)
scope.set_simple_trigger(CHANNEL, threshold_mv=0)

# Acquire multiple waveforms in rapid block mode
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    n_captures=CAPTURES,
)

# Retrieve the trigger time offset for each capture
offsets = scope.get_values_trigger_time_offset_bulk(0, CAPTURES - 1)
for i, (offset, unit) in enumerate(offsets):
    print(f"Segment {i}: offset = {offset} {unit.name}")

scope.close_unit()

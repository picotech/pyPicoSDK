import pypicosdk as psdk
from matplotlib import pyplot as plt

# Pico examples use inline argument values for clarity

# Capture configuration
SAMPLES = 1000
CAPTURES = 25

# Initialize scope
scope = psdk.ps6000a()
scope.open_unit()

# Setup siggen
scope.set_siggen(frequency=20E6, pk2pk=3, wave_type=psdk.WAVEFORM.SQUARE)

# Configure channel and trigger
scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V2)
scope.set_simple_trigger(channel=psdk.CHANNEL.A, threshold_mv=0)

# Convert desired sample rate to timebase
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)

# Perform rapid block capture
buffers, time_axis = scope.run_simple_rapid_block_capture(
    timebase=TIMEBASE,
    samples=SAMPLES,
    n_captures=CAPTURES,
)

# Retrieve trigger timing information for each segment
trigger_info = scope.get_trigger_info(0, CAPTURES)

scope.close_unit()

# Calculate dead time between captures
SAMPLE_INTERVAL_NS = time_axis[1] - time_axis[0]

dead_times = []
for prev, curr in zip(trigger_info[:-1], trigger_info[1:]):
    diff_samples = (curr["timeStampCounter"] - prev["timeStampCounter"]) & psdk.TIMESTAMP_COUNTER_MASK
    dead_samples = diff_samples - SAMPLES
    dead_times.append(dead_samples * SAMPLE_INTERVAL_NS)

print("Dead time between captures (ns):")
for i, dt in enumerate(dead_times, start=1):
    print(f"{i}->{i+1}: {dt:.2f}")

plt.plot(range(1, CAPTURES), dead_times, marker="o")
plt.xlabel("Capture index")
plt.ylabel("Dead time (ns)")
plt.title("Dead time between captures")
plt.grid(True)
plt.show()

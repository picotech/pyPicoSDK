import pypicosdk as psdk
import matplotlib.pyplot as plt
import numpy as np

# Initialize and configure scope
scope = psdk.ps6000a()
scope.open_unit(resolution=psdk.RESOLUTION._12BIT)

channel = psdk.CHANNEL.A
scope.set_channel(channel=channel, coupling=psdk.COUPLING.DC, range=psdk.RANGE.V1)
scope.set_simple_trigger(channel=channel, threshold_mv=200, direction=psdk.TRIGGER_DIR.RISING, auto_trigger_ms=0)

# Use the signal generator as a source
scope.set_siggen(frequency=1000, pk2pk=0.9, wave_type=psdk.WAVEFORM.SINE)

# Acquisition parameters
NSAMPLES = 1000
NCAPTURES = 100
TIMEBASE = scope.interval_to_timebase(20E-9)

uncorrected = []
corrected_time_axes = []
offsets = []

for _ in range(NCAPTURES):
    buffers, time_axis = scope.run_simple_block_capture(
        timebase=TIMEBASE,
        samples=NSAMPLES,
        ratio_mode=psdk.RATIO_MODE.TRIGGER,
    )
    waveform = buffers[channel]
    uncorrected.append(waveform)
    offset_ns = scope.get_trigger_time_offset(psdk.TIME_UNIT.NS)
    offsets.append(offset_ns)
    corrected_time_axes.append(np.array(time_axis) - offset_ns)

scope.close_unit()

# Calculate statistics of trigger offsets
offsets_np = np.array(offsets)
print(f"Mean trigger offset: {np.mean(offsets_np):.2f} ns")
print(f"Std dev trigger offset: {np.std(offsets_np):.2f} ns")

# Plot uncorrected, corrected, and histogram
fig, axes = plt.subplots(3, 1, figsize=(10, 12))

for wf in uncorrected:
    axes[0].plot(time_axis, wf, alpha=0.3)
axes[0].set_title(f"Uncorrected Waveforms ({NCAPTURES} captures)")
axes[0].set_xlabel("Time (ns)")
axes[0].set_ylabel("Amplitude (mV)")
axes[0].grid(True)

for wf, t_corr in zip(uncorrected, corrected_time_axes):
    axes[1].plot(t_corr, wf, alpha=0.3)
axes[1].set_title("Waveforms corrected with trigger_time_offset")
axes[1].set_xlabel("Corrected Time (ns)")
axes[1].set_ylabel("Amplitude (mV)")
axes[1].grid(True)

axes[2].hist(offsets_np, bins=20, edgecolor='black')
axes[2].set_title("Histogram of Trigger Time Offsets")
axes[2].set_xlabel("Offset (ns)")
axes[2].set_ylabel("Count")
axes[2].grid(True)

plt.tight_layout()
plt.show()


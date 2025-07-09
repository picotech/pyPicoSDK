import pypicosdk as psdk
import matplotlib.pyplot as plt
import numpy as np

# Pico examples use inline argument values for clarity


# Scope setup
scope = psdk.ps6000a()
scope.open_unit(resolution=psdk.RESOLUTION._12BIT)

# Configure channels
scope.set_channel(channel=psdk.CHANNEL.A, coupling=psdk.COUPLING.DC, range=psdk.RANGE.V1)
scope.set_channel(channel=psdk.CHANNEL.B, enabled=0, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)
scope.set_channel(channel=psdk.CHANNEL.C, enabled=0, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)
scope.set_channel(channel=psdk.CHANNEL.D, enabled=0, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)

# Configure an advanced trigger on Channel A at 200 mV
scope.set_advanced_trigger(
    channel=psdk.CHANNEL.A,
    state=psdk.PICO_TRIGGER_STATE.TRUE,
    direction=psdk.PICO_THRESHOLD_DIRECTION.PICO_RISING,
    threshold_mode=psdk.PICO_THRESHOLD_MODE.PICO_LEVEL,
    threshold_upper_mv=200,
    threshold_lower_mv=200,
)

# Use the signal generator as a source
scope.set_siggen(frequency=1000, pk2pk=0.9, wave_type=psdk.WAVEFORM.SINE)

# Acquisition parameters
NSAMPLES = 1000
NCAPTURES = 100
TIMEBASE = scope.sample_rate_to_timebase(50, psdk.SAMPLE_RATE.MSPS)

uncorrected = []
corrected_time_axes = []
offsets = []

for _ in range(NCAPTURES):
    # Capture a single waveform requesting trigger information
    buffers, time_axis = scope.run_simple_block_capture(
        timebase=TIMEBASE,
        samples=NSAMPLES,
        ratio_mode=psdk.RATIO_MODE.TRIGGER,
    )
    waveform = buffers[psdk.CHANNEL.A]
    uncorrected.append(waveform)

    # Retrieve trigger offset in nanoseconds and store corrected time axis
    # Offsets smaller than roughly one-tenth of the sample period may not be
    # reliable due to driver interpolation between samples.
    offset_ns = scope.get_trigger_time_offset(psdk.TIME_UNIT.NS)
    offsets.append(offset_ns)
    corrected_time_axes.append(np.array(time_axis) - offset_ns)

scope.close_unit()

# Calculate statistics of trigger offsets
offsets_np = np.array(offsets)
print(f"Mean trigger offset: {np.mean(offsets_np):.2f} ns")
print(f"Std dev trigger offset: {np.std(offsets_np):.2f} ns")

# Plot uncorrected, corrected, and histogram of offsets
fig, (ax_uncorr, ax_corr, ax_hist) = plt.subplots(3, 1, figsize=(10, 12))

for wf in uncorrected:
    ax_uncorr.plot(time_axis, wf, alpha=0.3)
ax_uncorr.set_title(f"Uncorrected Waveforms ({NCAPTURES} captures)")
ax_uncorr.set_xlabel("Time (ns)")
ax_uncorr.set_ylabel("Amplitude (mV)")
ax_uncorr.grid(True)

for wf, t_corr in zip(uncorrected, corrected_time_axes):
    ax_corr.plot(t_corr, wf, alpha=0.3)
ax_corr.set_title("Waveforms corrected with trigger_time_offset")
ax_corr.set_xlabel("Corrected Time (ns)")
ax_corr.set_ylabel("Amplitude (mV)")
ax_corr.grid(True)

ax_hist.hist(offsets_np, bins=20, edgecolor="black")
ax_hist.set_title("Histogram of Trigger Time Offsets")
ax_hist.set_xlabel("Offset (ns)")
ax_hist.set_ylabel("Count")
ax_hist.grid(True)

plt.tight_layout()
plt.show()

import pypicosdk as psdk
import matplotlib.pyplot as plt
import numpy as np

# Scope setup
scope = psdk.ps6000a()
scope.open_unit(resolution=psdk.RESOLUTION._12BIT)

# Configure channel and trigger
channel = psdk.CHANNEL.A
scope.set_channel(channel=channel, coupling=psdk.COUPLING.DC, range=psdk.RANGE.mV500)
scope.set_simple_trigger(channel=channel, threshold_mv=200,
                         direction=psdk.TRIGGER_DIR.RISING, auto_trigger_ms=0)

# Use the signal generator as a source
scope.set_siggen(frequency=1000, pk2pk=0.9, wave_type=psdk.WAVEFORM.SINE)

# Acquisition parameters
NSAMPLES = 1000
NCAPTURES = 100
TIMEBASE = scope.interval_to_timebase(20E-9)

uncorrected = []
corrected_time_axes = []

for _ in range(NCAPTURES):
    # Capture a single waveform
    buffers, time_axis = scope.run_simple_block_capture(timebase=TIMEBASE, samples=NSAMPLES)
    waveform = buffers[channel]
    uncorrected.append(waveform)

    # Retrieve trigger offset in nanoseconds and store corrected time axis
    offset_ns = scope.get_trigger_time_offset(psdk.TIME_UNIT.NS)
    corrected_time_axes.append(np.array(time_axis) - offset_ns)

scope.close_unit()

# Plot uncorrected and corrected waveforms
fig, (ax_uncorr, ax_corr) = plt.subplots(2, 1, figsize=(10, 8))

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

plt.tight_layout()
plt.show()

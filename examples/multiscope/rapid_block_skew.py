"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Trigger skew statistics between two or more PicoScope 6000E devices

Description:
  Runs a long MultiScope calibration (hundreds of rapid-block segments of the
  same edge) and plots two histograms: how late each follower's AUX trigger
  fires relative to the master, and what is left after the trigger time
  stamps have been used to line the records up. The first is the raw AUX
  path; the second is what run_simple_block_capture() and
  run_simple_rapid_block_capture() deliver.

Requirements:
- Two or more PicoScope 6000E units
- A 10 MHz reference into every REF IN (or the master AWG, see REFERENCE)
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup (diagrams in README.md next to this file):
  - 10 MHz reference -> rear REF IN of every scope
  - Master AUX I/O -> AUX I/O of every follower
  - Master AWG out -> BNC tee -> Channel A of every scope, equal-length leads
"""
from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Serial numbers of the scopes, and the master's serial (None = first in SERIALS).
# See block_overlay.py.
SERIALS = psdk.MultiScope.discover()
MASTER = None

# "external": a 10 MHz source on every REF IN. "master_awg": the master AWG is the reference.
REFERENCE = "external"

CAPTURES = 500
SAMPLES = 10_000

group = psdk.MultiScope(SERIALS, master=MASTER)
group.open_unit()
print("Master:", group.serials[0], " Followers:", group.serials[1:])
print("Locked to the external reference:", group.wait_for_lock(3.0), group.reference_status)

group.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.mV500, coupling=psdk.COUPLING.DC_50OHM)
if REFERENCE == "master_awg":
    group.use_master_awg_as_reference()
group.set_siggen(frequency=1_000, pk2pk=1.8, wave_type=psdk.WAVEFORM.SQUARE)
group.set_simple_trigger(psdk.CHANNEL.A, threshold=0)
TIMEBASES = group.sample_rate_to_timebase(5, psdk.SAMPLE_RATE.GSPS)

# The calibration itself is the measurement: one rapid block of CAPTURES segments
cal = group.calibrate(TIMEBASES, channel=psdk.CHANNEL.A, captures=CAPTURES, samples=SAMPLES)
interval_ns = cal.interval_ns

# Show the result on a real rapid block capture too: every segment is aligned on its own
data, time_axis = group.run_simple_rapid_block_capture(TIMEBASES, SAMPLES, captures=20)
segment_lag = group.last_alignment.lag_ns

group.close_unit()

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
for fc in cal.followers:
    raw_ns = np.array(fc.lag_ns)
    residual_ns = np.array(fc.residual_samples) * interval_ns
    print(f"{fc.serial}: AUX trigger lag {raw_ns.mean():.0f} ns, std {raw_ns.std():.1f} ns "
          f"({raw_ns.std() / interval_ns:.0f} samples); after time-stamp alignment std "
          f"{residual_ns.std():.2f} ns ({residual_ns.std() / interval_ns:.2f} samples)")
    axes[0].hist(raw_ns, bins=40, alpha=0.7, label=fc.serial)
    axes[1].hist(residual_ns, bins=40, alpha=0.7, label=fc.serial)
axes[0].set_title(f"Raw AUX trigger lag over {CAPTURES} segments")
axes[0].set_xlabel("Follower trigger after master (ns)")
axes[1].set_title(f"Residual after time-stamp alignment ({interval_ns:g} ns samples)")
axes[1].set_xlabel("Residual (ns)")
for ax in axes:
    ax.set_ylabel("Segments")
    ax.grid(True)
    ax.legend()
plt.tight_layout()
plt.show()

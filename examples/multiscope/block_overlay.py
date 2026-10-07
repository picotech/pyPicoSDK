"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Synchronised block capture on two PicoScope 6000E devices

Description:
  Captures the same edge on both scopes, first with no compensation and then
  after MultiScope calibration, and overlays the records. The left plot shows
  the raw AUX trigger latency between the units; the right plot shows the
  same records lined up sample for sample. Each scope is set up through the
  single-scope API (master.set_channel, follower.set_channel); the group only
  opens, calibrates, captures and closes.

Requirements:
- Two PicoScope 6000E units (for more, set up each extra follower like the first)
- A 10 MHz reference into every REF IN (or the master AWG, see REFERENCE)
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup (diagrams in README.md next to this file):
  - 10 MHz reference -> rear REF IN of every scope
  - Master AUX I/O -> AUX I/O of every follower
  - Master AWG out -> BNC tee -> Channel A of every scope, equal-length leads
  - EXTERNAL_PULSE mode: after calibration the script asks you to move the tee from the
    master AWG to your own single-shot pulse source, then waits for the pulse
"""
from matplotlib import pyplot as plt
import pypicosdk as psdk

# Serial numbers of the scopes in the group. discover() lists every 6000E connected, in sorted
# order, which says nothing about the cabling. Replace it with e.g. ["JR001/001", "JR001/002"]
# to use only some of them.
SERIALS = psdk.MultiScope.discover()

# The master: the unit whose AUX drives the others and whose AWG feeds the tee. Set its serial
# number, e.g. "JR001/002". None makes the first serial in SERIALS the master.
MASTER = None

# Channel A coupling on every scope. DC_50OHM terminates the tee and is the only choice on a
# 6428E-D. DC (1 Mohm) works on every other model, for example when one unit's 50 ohm path is
# unavailable; the AWG amplitude below follows this setting.
COUPLING = psdk.COUPLING.DC_50OHM

# "external": a 10 MHz source on every REF IN.
# "master_awg": the master AWG is the reference (master AWG -> follower REF IN) and the first
#               follower's AWG supplies the test signal instead.
REFERENCE = "external"

# True: calibrate on the AWG edge as usual, then capture a single-shot pulse of your own on the
# same channel. The pulse must rise through PULSE_THRESHOLD_MV (0.6 Vpp of AWG square does too).
EXTERNAL_PULSE = False
PULSE_THRESHOLD_MV = 100

SAMPLES = 10_000

# Create the group and open both scopes. Opening and closing stay on the group: that is where
# it switches the master's AUX to TRIGGER_OUT, gives the follower its AUX trigger and starts
# watching the reference lock. The master moves to index 0; group.serials holds the order.
group = psdk.MultiScope(SERIALS, master=MASTER)
group.open_unit()
print("Master:", group.serials[0], " Followers:", group.serials[1:])
print("Locked to the external reference:", group.wait_for_lock(3.0), group.reference_status)

# From here each scope is an ordinary ps6000a object with the single-scope API
master = group[0]
follower = group[1]

# +/-500 mV: the widest range every 6000E model, 6428E-D included, has in common
master.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.mV500, coupling=COUPLING)
follower.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.mV500, coupling=COUPLING)

# 1 kHz square. 1.8 V open circuit gives 0.6 Vpp at two 50 ohm inputs on a tee. 1 Mohm inputs
# do not load the AWG, so they see the full open-circuit amplitude: 0.9 V keeps it in range.
# The master's AWG feeds the tee, unless it is busy as the follower's 10 MHz reference.
if REFERENCE == "master_awg":
    master.set_siggen(frequency=10e6, pk2pk=1.0, wave_type=psdk.WAVEFORM.SINE)
    stimulus = follower
else:
    stimulus = master
stimulus.set_siggen(frequency=1_000, pk2pk=1.8 if COUPLING == psdk.COUPLING.DC_50OHM else 0.9,
                    wave_type=psdk.WAVEFORM.SQUARE)

# Trigger the master only. The follower already triggers from the master's AUX pulse, so do
# not set a trigger on it. Keep this trigger unchanged after calibrate(): changing the trigger
# source or the timebase restarts the time-stamp counters the alignment relies on.
master.set_simple_trigger(psdk.CHANNEL.A, threshold=PULSE_THRESHOLD_MV if EXTERNAL_PULSE else 0)

# One timebase per scope, in group order: the same rate can be a different number on different
# models. Every group capture checks that the two sample intervals match.
TIMEBASES = (master.sample_rate_to_timebase(5, psdk.SAMPLE_RATE.GSPS),
             follower.sample_rate_to_timebase(5, psdk.SAMPLE_RATE.GSPS))

# Capturing and calibrating stay on the group: it arms the follower before the master, reads
# both trigger time stamps and lines the records up.

# Before: identical windows on every scope, nothing compensated
before, time_axis = group.run_simple_block_capture(TIMEBASES, SAMPLES, align=False)

# Calibrate: 64 rapid-block captures of the shared edge give each follower's AUX latency,
# its jitter and the constant offset between the units' trigger time-stamp counters
cal = group.calibrate(TIMEBASES, channel=psdk.CHANNEL.A, captures=64, samples=SAMPLES)
for fc in cal.followers:
    print(f"{fc.serial}: triggers {fc.latency_ns:.0f} ns after the master, jitter "
          f"{fc.jitter_ns:.0f} ns, time-stamp offset {fc.timestamp_offset:.1f} samples")

# After: followers are armed early and each record is cut to the master's window using the
# two trigger time stamps, so the edge lands on the same sample on every scope
if EXTERNAL_PULSE:
    input("Calibrated. Move the tee from the master AWG to your pulse source, then press Enter...")
    print("Fire the pulse now (Ctrl+C to abort)")
after, time_axis = group.run_simple_block_capture(TIMEBASES, SAMPLES)
info = group.last_alignment
print(f"Alignment: {info.mode}; follower lag this capture "
      f"{[f'{lag:.0f} ns' for lag in info.lag_ns[1:]]}")

# Release the devices from the driver
group.close_unit()

# Plot: raw records on the left, aligned on the right
fig, (ax_before, ax_after) = plt.subplots(1, 2, figsize=(12, 4.5), sharey=True)
for index, serial in enumerate(group.serials):
    label = f"{serial} ({'master' if index == 0 else 'follower'})"
    ax_before.plot(time_axis, before[index][psdk.CHANNEL.A], label=label)
    ax_after.plot(time_axis, after[index][psdk.CHANNEL.A], label=label)
ax_before.set_title("Before: same settings on every scope")
ax_after.set_title("After: calibrated, aligned from trigger time stamps")
for ax in (ax_before, ax_after):
    ax.set_xlabel("Time (ns)")
    ax.grid(True)
    ax.legend()
ax_before.set_ylabel("Amplitude (mV)")
plt.tight_layout()
plt.show()

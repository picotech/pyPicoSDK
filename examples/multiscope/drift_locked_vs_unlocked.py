"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Sample clock drift between two PicoScope 6000E devices, locked and unlocked

Description:
  Both scopes capture the same sine for a couple of seconds. The script times
  every zero crossing on each scope and plots how the follower's clock runs
  away from the master's along the record: a straight line whose slope is the
  frequency error in ppm when the follower is on its own crystal, and a flat
  line when both are locked to the 10 MHz reference. It captures once locked,
  then asks you to unplug the follower's REF IN and captures again.

Requirements:
- Two PicoScope 6000E units
- A 10 MHz reference into both REF IN connectors
- Python packages:
  (pip install) matplotlib numpy pypicosdk

Setup:
  - 10 MHz reference -> rear REF IN of both scopes
  - Master AUX I/O -> follower AUX I/O
  - Master AWG out -> BNC tee -> Channel A of both scopes
"""
import time

from matplotlib import pyplot as plt
import numpy as np
import pypicosdk as psdk

# Serial numbers of the scopes, and the master's serial (None = first in SERIALS).
# See block_overlay.py.
SERIALS = psdk.MultiScope.discover()
MASTER = None

SINE_HZ = 100_000
RECORD_SECONDS = 2.0
SAMPLE_RATE_MSPS = 10
POINTS = 200            # plotted points along the record, each the mean of a bin of crossings


def crossing_times(samples, interval_ns):
    """Times (ns) of the rising zero crossings and the number of each crossing.

    A 5-sample moving average removes single-sample noise excursions that would
    otherwise add a spurious crossing. Numbering crossings by counting whole
    periods between them keeps a missed or extra crossing from shifting every
    later one, which would otherwise show up as a fake step of one period.
    """
    y = np.convolve(samples.astype(np.float64), np.ones(5) / 5, mode='same')
    i = np.flatnonzero((y[:-1] < 0) & (y[1:] >= 0))
    t = (i - y[i] / (y[i + 1] - y[i])) * interval_ns
    period = np.median(np.diff(t))
    number = np.concatenate(([0], np.cumsum(np.rint(np.diff(t) / period)))).astype(int)
    return t, number


def drift_curve(data, interval_ns):
    """Accumulated timing difference follower - master (ns) versus record time (s)."""
    t_master, n_master = crossing_times(data[0][psdk.CHANNEL.A], interval_ns)
    t_follower, n_follower = crossing_times(data[1][psdk.CHANNEL.A], interval_ns)
    _, i_master, i_follower = np.intersect1d(n_master, n_follower, return_indices=True)
    t_master, t_follower = t_master[i_master], t_follower[i_follower]
    delta = (t_follower - t_follower[0]) - (t_master - t_master[0])
    record_s = (t_master - t_master[0]) * 1e-9
    bins = np.array_split(np.arange(delta.size), POINTS)
    return (np.array([record_s[b].mean() for b in bins]),
            np.array([delta[b].mean() for b in bins]))


group = psdk.MultiScope(SERIALS, master=MASTER)
group.open_unit()
print("Locked to the external reference:", group.wait_for_lock(3.0), group.reference_status)

group.set_channel(psdk.CHANNEL.A, range=psdk.RANGE.mV500, coupling=psdk.COUPLING.DC_50OHM)
group.set_siggen(frequency=SINE_HZ, pk2pk=1.8, wave_type=psdk.WAVEFORM.SINE)
group.set_simple_trigger(psdk.CHANNEL.A, threshold=0)
TIMEBASES = group.sample_rate_to_timebase(SAMPLE_RATE_MSPS, psdk.SAMPLE_RATE.MSPS)
interval_ns = group[0].get_timebase(TIMEBASES[0], 1)['Interval(ns)']
samples = int(RECORD_SECONDS * 1e9 / interval_ns)
print(f"Capturing {samples:,} samples per scope at {interval_ns:g} ns")

# No calibration needed: only the rate difference inside each record is measured
data_locked, _ = group.run_simple_block_capture(TIMEBASES, samples, pre_trig_percent=0,
                                                output_unit='adc', align=False)
time_locked, drift_locked = drift_curve(data_locked, interval_ns)

input(f"Unplug the 10 MHz REF IN cable from the follower ({group.serials[1]}) and press Enter...")
for _ in range(60):                      # the driver reports the change within a second or so
    if group.reference_status[1] == psdk.CLOCK_REFERENCE.INTERNAL_REF:
        break
    time.sleep(0.5)
print("Follower clock:", group.reference_status[1].name)
data_unlocked, _ = group.run_simple_block_capture(TIMEBASES, samples, pre_trig_percent=0,
                                                  output_unit='adc', align=False)
time_unlocked, drift_unlocked = drift_curve(data_unlocked, interval_ns)
input("Plug the REF IN cable back in and press Enter...")
print("Follower clock after replug:", "locked" if group.wait_for_lock(5.0) else "still internal")

group.close_unit()

slope_ppm = np.polyfit(time_unlocked, drift_unlocked, 1)[0] * 1e-9 * 1e6
print(f"Unlocked: the follower clock differs from the master by {slope_ppm:+.2f} ppm "
      f"({drift_unlocked[-1]:+.0f} ns over {time_unlocked[-1]:.1f} s)")
print(f"Locked:   {drift_locked[-1]:+.0f} ns over {time_locked[-1]:.1f} s")

plt.plot(time_locked, drift_locked, label="locked to 10 MHz reference")
plt.plot(time_unlocked, drift_unlocked, label=f"unlocked ({slope_ppm:+.2f} ppm)")
plt.xlabel("Time into record (s)")
plt.ylabel("Follower minus master timing (ns)")
plt.title("Sample clock drift between two 6000E units")
plt.grid(True)
plt.legend()
plt.show()

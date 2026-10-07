"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Live 10 MHz reference lock status for two or more PicoScope 6000E devices

Description:
  Opens every scope and prints which clock each one is running from whenever
  that changes. Unplug the 10 MHz reference from a scope and watch it drop to
  INTERNAL_REF; plug it back in and watch it lock again. The status comes
  from the driver's external reference callback, which MultiScope registers
  on every unit.

Requirements:
- Two or more PicoScope 6000E units
- A 10 MHz reference into every REF IN (or the master AWG, see REFERENCE)
- Python packages:
  (pip install) pypicosdk

Setup:
  - 10 MHz reference -> rear REF IN of every scope
  - REFERENCE = "master_awg": master AWG out -> REF IN of every follower instead
"""
import time
import pypicosdk as psdk

# Serial numbers of the scopes, and the master's serial (None = first in SERIALS).
# See block_overlay.py.
SERIALS = psdk.MultiScope.discover()
MASTER = None

# "external": a 10 MHz source on every REF IN. "master_awg": the master AWG is the reference.
REFERENCE = "external"

WATCH_SECONDS = 60

group = psdk.MultiScope(SERIALS, master=MASTER)
group.open_unit()
if REFERENCE == "master_awg":
    group.use_master_awg_as_reference()

print("Watching the reference lock for", WATCH_SECONDS, "s. Unplug and replug a REF IN cable. "
      "Ctrl+C to stop.")
print("All locked:", group.wait_for_lock(3.0))

last = None
deadline = time.monotonic() + WATCH_SECONDS
try:
    while time.monotonic() < deadline:
        status = group.reference_status
        if status != last:
            stamp = time.strftime("%H:%M:%S")
            for serial, reference in zip(group.serials, status):
                name = reference.name if reference is not None else "not reported yet"
                print(f"{stamp}  {serial}: {name}")
            last = status
        time.sleep(0.1)
except KeyboardInterrupt:
    pass

group.close_unit()

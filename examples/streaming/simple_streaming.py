"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Hardware-agnostic streaming — PicoScope 6000E / 3000E / 5000E / 5000D

Description:
  Streams Channel A continuously for CAPTURE_SECONDS using StreamingSession,
  the supported hardware-agnostic streaming loop. The session owns buffer
  registration, rotation and polling for every driver, so the ONLY line that
  changes between devices is the SCOPE_CLASS below.

  Compare with the other examples in this folder, which drive the low-level
  streaming calls (set_data_buffer / run_streaming /
  get_streaming_latest_values) directly: that surface exposes each driver's
  own buffer model, so those scripts are written per-device. This example is
  the streaming equivalent of simple_block_capture.py: the wrapper owns the
  sequence, the user owns the samples.

Key Concepts:
  - StreamingSession yields chunks: each chunk holds a private numpy copy of
    the new samples per channel, safe to keep or hand to another thread.
  - Chunks arrive in the capture's native dtype (no upcasting) and carry
    over-range, trigger and auto-stop flags.
  - The session surfaces capability walls instead of hiding them: a
    configuration the connected driver cannot express raises PicoSDKException
    at construction rather than degrading silently.
  - Achievable sample rates still differ per device family. The session
    reports the driver's actual interval via actual_sample_interval.

Requirements:
  - Any streaming-capable PicoScope (6000E, 3000E, 5000E, 5000D)
  - Python packages: numpy pypicosdk

Setup:
  - Connect a signal to Channel A (or use the AWG below)
  - Set SCOPE_CLASS to match your device
"""
import time
import numpy as np
import pypicosdk as psdk


# ============================================================================
# CONFIGURATION
# ============================================================================

SCOPE_CLASS = psdk.ps6000a      # ps6000a / psospa / ps5000a — change this only

SAMPLE_INTERVAL = 100           # requested interval between samples
TIME_UNITS = psdk.TIME_UNIT.NS  # 100 ns -> 10 MS/s (driver rounds to nearest)
CAPTURE_SECONDS = 5             # stop after this much wall-clock time
DATA_TYPE = psdk.DATA_TYPE.INT16_T  # native on every driver


# ============================================================================
# HARDWARE SETUP
# ============================================================================

scope = SCOPE_CLASS()
scope.open_unit()
print(f"Connected to PicoScope: {scope.get_unit_serial()}")

scope.set_channel(channel=psdk.CHANNEL.A, range=psdk.RANGE.V1)

# Optionally drive a test signal via the built-in AWG
scope.set_siggen(frequency=10e3, pk2pk=1.5, wave_type=psdk.WAVEFORM.SINE)


# ============================================================================
# STREAM
# ============================================================================

total_samples = 0
running_min = None
running_max = None
start = time.perf_counter()

with psdk.StreamingSession(
    scope,
    sample_interval=SAMPLE_INTERVAL,
    time_units=TIME_UNITS,
    datatype=DATA_TYPE,
) as stream:
    print(f"Actual sample interval : {stream.actual_sample_interval:.4g} "
          f"(requested {SAMPLE_INTERVAL})")
    print(f"Streaming for {CAPTURE_SECONDS} s...  (Ctrl+C to stop early)\n")

    try:
        last_print = start
        for chunk in stream:
            samples = chunk.data[psdk.CHANNEL.A]
            total_samples += len(samples)

            # Example per-chunk processing: track the signal envelope
            if len(samples):
                lo, hi = samples.min(), samples.max()
                running_min = lo if running_min is None else min(running_min, lo)
                running_max = hi if running_max is None else max(running_max, hi)

            now = time.perf_counter()
            if now - last_print >= 1.0:
                rate_ms = total_samples / (now - start) / 1e6
                print(f"  {total_samples:,} samples  ({rate_ms:.2f} MS/s average)")
                last_print = now

            if now - start >= CAPTURE_SECONDS:
                break
    except KeyboardInterrupt:
        print("\nStopped by user.")

# Leaving the `with` block stops the capture on the device.
scope.close_unit()


# ============================================================================
# SUMMARY
# ============================================================================

elapsed = time.perf_counter() - start
print(f"\n{'-' * 50}")
print(f"Samples captured : {total_samples:,} in {elapsed:.2f} s "
      f"({total_samples / elapsed / 1e6:.2f} MS/s)")
if running_min is not None:
    print(f"Signal envelope  : {running_min} .. {running_max} ADC counts")
print(f"{'-' * 50}")

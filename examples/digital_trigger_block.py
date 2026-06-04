"""
Copyright (C) 2025-2026 Pico Technology Ltd. See LICENSE file for terms.

Digital-input trigger block capture for a PicoScope 5000A MSO

Description:
  Arms a block capture on a rising edge of digital channel D0 and reads back
  the digital port. No analog channel is required - the capture is timed and
  triggered entirely from the digital port.

Requirements:
- PicoScope 5000A MSO (e.g. 5242D MSO)
- Python packages:
  (pip install) pypicosdk

Setup:
  - Connect your logic signal to D0 on digital connector PORT0
"""
import pypicosdk as psdk

SAMPLES = 5_000
LOGIC_THRESHOLD_V = 1.5          # logic threshold on the fixed +/-5 V digital range

scope = psdk.ps5000a()
scope.open_unit(resolution=psdk.RESOLUTION.BIT_8)

# Enable digital PORT0 (channels D0..D7) and set the logic threshold in volts.
scope.set_digital_port(psdk.DIGITAL_PORT.PORT0, enabled=True, logic_level_v=LOGIC_THRESHOLD_V)

# Trigger when the PORT0 source condition is met...
scope.set_trigger_channel_conditions(
    [(psdk.DIGITAL_PORT.PORT0, psdk.TRIGGER_STATE.TRUE)]
)
# ...specifically on a rising edge of D0.
scope.set_trigger_digital_port_properties(
    channels=[psdk.DIGITAL_CHANNEL.CHANNEL0],
    directions=[psdk.DIGITAL_DIRECTION.DIRECTION_RISING],
)

# A digital port counts as an enabled channel, so the timebase helpers work
# without enabling any analog channel.
timebase = scope.sample_rate_to_timebase(sample_rate=10, unit=psdk.SAMPLE_RATE.MSPS)
print("Actual sample rate:", scope.get_actual_sample_rate())

# Allocate the digital port buffer, arm, and wait for the edge.
scope.set_data_buffer(psdk.DIGITAL_PORT.PORT0, SAMPLES)
scope.set_auto_trigger_microseconds(0)        # wait indefinitely for the edge
scope.run_block_capture(timebase, SAMPLES, pre_trig_percent=20)
samples = scope.get_values(SAMPLES)
print(f"Captured {samples} samples on PORT0 after the D0 rising edge.")

scope.close_unit()

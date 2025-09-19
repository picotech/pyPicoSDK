<!-- Copyright (C) 2025-2025 Pico Technology Ltd. See LICENSE file for terms. -->
# Measurement examples

These examples demonstrate one of many methods of measuring the ADC data from your PicoScope.
When making measurements yourself, always verify that your method is suitable for your hardware, signal characteristics, and accuracy requirements.

## Using measurements.py

Each of these examples import particular measurements from measurements.py as some are repeated
in different examples i.e. max, min, top and base.

The import will be similar to the following:

`from measurements import pk2pk, amplitude`

If you're including measurements.py for your own project, verify that the methods used to calculate
these measurements are accurate and suitable for your data.

As per LICENCE.md these measurements can be customised and adjusted in your own projects to suit
your data.